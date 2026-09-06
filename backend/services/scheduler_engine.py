"""有限产能排程引擎 - 综合设备产能与人员产能双重约束"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from backend.models.all_models import *
import uuid


class SchedulerEngine:
    """有限产能排程引擎"""
    
    def run(self, db: Session, data: dict) -> List[ScheduleTask]:
        """
        data: {
            products: [{product_id, quantity, due_date}],
            locked_task_ids: []
        }
        """
        products_data = data.get('products', [])
        locked_ids = data.get('locked_task_ids', [])
        batch_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
        
        # 获取所有需要的数据
        all_devices = db.query(Device).all()
        all_employees = db.query(Employee).all()
        
        # 构建排程任务列表
        all_tasks = []
        
        # 保留锁定的任务
        locked_tasks = []
        if locked_ids:
            locked_tasks = db.query(ScheduleTask).filter(ScheduleTask.id.in_(locked_ids)).all()
        
        # 清除旧的未锁定任务
        db.query(ScheduleTask).filter(
            ScheduleTask.batch_id != batch_id,
            ~ScheduleTask.id.in_(locked_ids)
        ).delete(synchronize_session=False)
        
        schedule_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 收集所有设备的占用时间线
        device_timelines = {}  # device_id -> [(start, end), ...]
        employee_timelines = {}  # employee_id -> [(start, end), ...]
        
        # 加载锁定任务的时间占用
        for lt in locked_tasks:
            if lt.device_id:
                device_timelines.setdefault(lt.device_id, []).append((lt.start_time, lt.end_time))
            if lt.employee_id:
                employee_timelines.setdefault(lt.employee_id, []).append((lt.start_time, lt.end_time))
        
        for prod_data in products_data:
            product_id = prod_data['product_id']
            quantity = prod_data['quantity']
            due_date = datetime.fromisoformat(prod_data['due_date'].replace('Z', '+00:00')) if 'due_date' in prod_data else datetime.now() + timedelta(days=7)
            
            product = db.query(Product).get(product_id)
            if not product:
                raise ValueError(f"产品ID {product_id} 不存在")
            
            route = db.query(ProductRoute).filter(ProductRoute.product_id == product_id).first()
            if not route:
                raise ValueError(f"产品 {product.name} 未配置工艺路线")
            
            steps = sorted(route.steps, key=lambda s: s.step_order)
            
            # 为每一步工序分配设备和人员
            step_end_time = schedule_start
            for step in steps:
                process = step.process
                process_time_per_unit = step.process_time_per_unit
                total_minutes = quantity * process_time_per_unit
                
                # 获取可用设备
                available_devices = self._get_available_devices(process)
                
                # 获取可用员工（具有该工序和设备技能）
                available_employees = self._get_available_employees(process, available_devices, db)
                
                if not available_devices:
                    raise ValueError(f"工序 '{process.name}' 没有可用设备")
                
                # 决定是否拆分
                can_split = process.is_splittable and len(available_devices) > 1
                
                if can_split and len(available_devices) > 1:
                    # 并行拆分到多台设备
                    per_device_qty = quantity / len(available_devices)
                    for i, device in enumerate(available_devices):
                        dev_qty = int(per_device_qty) if i < len(available_devices) - 1 else quantity - int(per_device_qty) * (len(available_devices) - 1)
                        if dev_qty <= 0:
                            continue
                        
                        dev_minutes = dev_qty * process_time_per_unit
                        employee = available_employees[i % len(available_employees)] if available_employees else None
                        
                        segments = self._find_time_slots(
                            device, employee, dev_minutes, step_end_time,
                            device_timelines, employee_timelines, db
                        )
                        tasks = self._create_task_segments(
                            db, batch_id, product, process, step, device, employee,
                            dev_qty, segments, dev_minutes, due_date, prod_data
                        )
                        all_tasks.extend(tasks)
                else:
                    # 单台设备连续加工
                    device = available_devices[0]
                    employee = available_employees[0] if available_employees else None
                    
                    segments = self._find_time_slots(
                        device, employee, total_minutes, step_end_time,
                        device_timelines, employee_timelines, db
                    )
                    tasks = self._create_task_segments(
                        db, batch_id, product, process, step, device, employee,
                        quantity, segments, total_minutes, due_date, prod_data
                    )
                    all_tasks.extend(tasks)
                
                # 更新该步骤的最晚结束时间作为下一步的最早开始时间
                step_tasks = [t for t in all_tasks if t.route_step_id == step.id]
                if step_tasks:
                    step_end_time = max(t.end_time for t in step_tasks)
        
        db.commit()
        return all_tasks
    
    def _get_available_devices(self, process: Process) -> List[Device]:
        """获取工序可用的设备列表"""
        allowed_status = {'available', 'normal'}
        devices = []
        seen_ids = set()
        
        # 绑定的具体设备
        for d in process.devices:
            if d.status in allowed_status and d.id not in seen_ids:
                devices.append(d)
                seen_ids.add(d.id)
        
        # 绑定的设备组中的设备
        for dg in process.device_groups:
            for d in dg.devices:
                if d.status in allowed_status and d.id not in seen_ids:
                    devices.append(d)
                    seen_ids.add(d.id)
        
        return devices
    
    def _get_available_employees(self, process: Process, devices: List[Device], db: Session) -> List[Employee]:
        """获取同时具备工序权限和设备权限的员工"""
        device_ids = [d.id for d in devices]
        employees = db.query(Employee).filter(
            Employee.id.in_(
                db.query(employee_process.c.employee_id).filter(
                    employee_process.c.process_id == process.id
                )
            )
        ).filter(
            Employee.id.in_(
                db.query(employee_device.c.employee_id).filter(
                    employee_device.c.device_id.in_(device_ids)
                )
            )
        ).all()
        return employees
    
    def _find_time_slots(self, device: Device, employee, total_minutes: float,
                         earliest_start: datetime, device_timelines: dict, employee_timelines: dict,
                         db: Session) -> list:
        """找到设备和员工都空闲的时间槽列表，支持跨天自动拆分。
        返回: [(start, end, minutes_in_segment), ...]"""
        segments = []
        remaining_minutes = total_minutes
        current = earliest_start
        max_iterations = 5000
        iteration = 0
        last_current = None
        
        while remaining_minutes > 0 and iteration < max_iterations:
            iteration += 1
            
            if last_current and current == last_current:
                current += timedelta(hours=1)
            last_current = current
            
            dev_work_start, dev_work_end = self._get_device_work_hours(device)
            if not self._is_in_work_time(current, dev_work_start, dev_work_end):
                current = self._next_work_start(current, dev_work_start)
                continue
            
            emp_shift = None
            if employee:
                emp_shift = self._get_employee_shift(employee, current, db)
                if not self._is_in_shift(current, emp_shift):
                    current = self._next_shift_start(current, emp_shift)
                    continue
            
            # 计算当前可用的最大连续时长
            max_available = remaining_minutes
            
            # 班次约束
            if emp_shift:
                shift_end_dt = self._get_shift_end(current, emp_shift)
                shift_remaining = (shift_end_dt - current).total_seconds() / 60
                max_available = min(max_available, shift_remaining)
            
            # 设备工作时间约束
            dev_end_h, dev_end_m = map(int, dev_work_end.split(':'))
            dev_end_dt = current.replace(hour=dev_end_h, minute=dev_end_m, second=0, microsecond=0)
            if dev_work_start <= dev_work_end:
                if dev_end_dt <= current:
                    dev_end_dt += timedelta(days=1)
            else:
                if current.hour >= int(dev_work_start.split(':')[0]):
                    dev_end_dt += timedelta(days=1)
            dev_remaining = (dev_end_dt - current).total_seconds() / 60
            max_available = min(max_available, dev_remaining)
            
            if max_available <= 0:
                if emp_shift:
                    current = self._next_shift_start(current, emp_shift)
                else:
                    current = self._next_work_start(current, dev_work_start)
                continue
            
            # 检查设备占用
            tentative_end = current + timedelta(minutes=max_available)
            dev_tl = device_timelines.get(device.id, [])
            block_end = self._first_block_end(current, dev_tl)
            if block_end and block_end < tentative_end:
                max_available = min(max_available, (block_end - current).total_seconds() / 60)
                if max_available <= 0:
                    current = block_end
                    continue
            
            # 检查员工占用
            if employee:
                emp_tl = employee_timelines.get(employee.id, [])
                block_end = self._first_block_end(current, emp_tl)
                if block_end:
                    emp_max = (block_end - current).total_seconds() / 60
                    max_available = min(max_available, emp_max)
                    if max_available <= 0:
                        current = block_end
                        continue
            
            segment_minutes = max_available
            segment_end = current + timedelta(minutes=segment_minutes)
            
            if segment_minutes > 0:
                segments.append((current, segment_end, segment_minutes))
                remaining_minutes -= segment_minutes
                device_timelines.setdefault(device.id, []).append((current, segment_end))
                if employee:
                    employee_timelines.setdefault(employee.id, []).append((current, segment_end))
            current = segment_end
        
        if remaining_minutes > 0:
            raise ValueError(f"无法为设备 {device.name} 找到足够的可用时间槽 (剩余 {remaining_minutes:.0f} 分钟)")
        return segments
    
    def _get_device_work_hours(self, device: Device) -> tuple:
        """获取设备工作时间"""
        if device.work_start_time and device.work_end_time:
            return device.work_start_time, device.work_end_time
        if device.group:
            return device.group.work_start_time, device.group.work_end_time
        return '00:00', '23:59'
    
    def _is_in_work_time(self, dt: datetime, work_start: str, work_end: str) -> bool:
        """检查是否在工作时间内"""
        t = dt.strftime('%H:%M')
        if work_start <= work_end:
            return work_start <= t < work_end
        else:
            # 跨天班次
            return t >= work_start or t < work_end
    
    def _next_work_start(self, dt: datetime, work_start: str) -> datetime:
        """下一个工作开始时间"""
        h, m = map(int, work_start.split(':'))
        next_dt = dt.replace(hour=h, minute=m, second=0, microsecond=0)
        if next_dt <= dt:
            next_dt += timedelta(days=1)
        return next_dt
    
    def _get_employee_shift(self, employee: Employee, dt: datetime, db: Session):
        """获取员工在指定日期的班次"""
        if employee.shift:
            return employee.shift
        if employee.rotation:
            return self._calculate_rotation_shift(employee, dt, db)
        return None
    
    def _calculate_rotation_shift(self, employee: Employee, dt: datetime, db: Session):
        """计算轮班模式下的班次"""
        if not employee.rotation_start_date or not employee.rotation_start_shift:
            return None
        
        start_date = datetime.strptime(employee.rotation_start_date, '%Y-%m-%d')
        days_diff = (dt.date() - start_date.date()).days
        
        if days_diff < 0:
            return None
        
        rotation = employee.rotation
        shifts = sorted(rotation.shift_rotations, key=lambda s: s.sequence_order if hasattr(s, 'sequence_order') else 0)
        if not shifts:
            return None
        
        # 找到起始班次的索引
        start_idx = 0
        for i, s in enumerate(shifts):
            if s.id == employee.rotation_start_shift_id:
                start_idx = i
                break
        
        cycle_days = rotation.cycle_days or len(shifts)
        shift_index = (start_idx + (days_diff % cycle_days)) % len(shifts)
        return shifts[shift_index]
    
    def _is_in_shift(self, dt: datetime, shift) -> bool:
        """检查时间是否在班次内"""
        if not shift:
            return True  # 无班次限制
        t = dt.strftime('%H:%M')
        if shift.start_time <= shift.end_time:
            return shift.start_time <= t < shift.end_time
        else:
            return t >= shift.start_time or t < shift.end_time
    
    def _next_shift_start(self, dt: datetime, shift) -> datetime:
        """下一个班次开始时间"""
        if not shift:
            return dt
        h, m = map(int, shift.start_time.split(':'))
        next_dt = dt.replace(hour=h, minute=m, second=0, microsecond=0)
        if next_dt <= dt:
            next_dt += timedelta(days=1)
        return next_dt
    
    def _get_shift_end(self, dt: datetime, shift) -> datetime:
        """获取当前班次结束时间"""
        if not shift:
            return dt.replace(hour=23, minute=59, second=59)
        h, m = map(int, shift.end_time.split(':'))
        end_dt = dt.replace(hour=h, minute=m, second=0, microsecond=0)
        # 跨天班次 (end < start)
        if shift.end_time < shift.start_time:
            if dt.hour >= int(shift.start_time.split(':')[0]):
                end_dt += timedelta(days=1)
        return end_dt
    
    def _first_block_end(self, current: datetime, timeline: list) -> datetime:
        """找到时间线上第一个阻塞段的结束时间，若无阻塞返回None"""
        if not timeline:
            return None
        sorted_tl = sorted(timeline, key=lambda x: x[0])
        for ts, te in sorted_tl:
            if ts < current < te:
                return te
            if ts >= current:
                return None
        return None

    def _is_time_busy(self, start: datetime, end: datetime, timeline: list) -> bool:
        """检查时段是否与时间线冲突"""
        for ts, te in timeline:
            if start < te and end > ts:
                return True
        return False
    
    def _next_free_time(self, current: datetime, timeline: list) -> datetime:
        """找到下一个空闲时间"""
        if not timeline:
            return current
        sorted_timeline = sorted(timeline, key=lambda x: x[0])
        for ts, te in sorted_timeline:
            if current < te:
                if current < ts:
                    return current
                return te
        return current
    
    def _create_task_segments(self, db: Session, batch_id: str, product: Product, process: Process,
                              step: RouteStep, device: Device, employee, total_qty: float,
                              segments: list, total_minutes: float, due_date: datetime,
                              prod_data: dict) -> List[ScheduleTask]:
        """根据时间槽分段列表创建任务，按各段时间比例分配数量，并更新时间线"""
        tasks = []
        total_seg_minutes = sum(s[2] for s in segments)
        for start_t, end_t, seg_minutes in segments:
            # 按时间比例分配数量
            seg_qty = total_qty * (seg_minutes / total_seg_minutes) if total_seg_minutes > 0 else 0
            if seg_qty < 1 and total_qty >= 1:
                # 确保至少分到整数
                seg_qty = round(seg_qty, 2)
            task = self._create_task(
                db, batch_id, product, process, step, device, employee,
                seg_qty, start_t, end_t, seg_minutes, due_date, prod_data, db
            )
            tasks.append(task)
        return tasks

    def _create_task(self, db: Session, batch_id: str, product: Product, process: Process,
                     step: RouteStep, device: Device, employee, quantity: float,
                     start_time: datetime, end_time: datetime, duration: float,
                     due_date: datetime, prod_data: dict, db_session: Session) -> ScheduleTask:
        """创建排程任务记录"""
        category_name = product.category.name if product.category else ''
        device_group_name = device.group.name if device.group else ''
        employee_group_name = employee.group.name if employee and employee.group else ''
        shift_name = employee.shift.name if employee and employee.shift else ''
        
        task = ScheduleTask(
            batch_id=batch_id,
            product_id=product.id,
            product_name=product.name,
            product_category=category_name,
            route_step_id=step.id,
            process_id=process.id,
            process_name=process.name,
            step_order=step.step_order,
            device_id=device.id,
            device_name=device.name,
            device_group_name=device_group_name,
            employee_id=employee.id if employee else None,
            employee_name=employee.name if employee else '',
            employee_group_name=employee_group_name,
            shift_name=shift_name,
            quantity=quantity,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            due_date=due_date,
            is_locked=False
        )
        db_session.add(task)
        db_session.flush()
        return task
    
    def rerun(self, db: Session, batch_id: str, products_data: list) -> List[ScheduleTask]:
        """重排（保留锁定的任务）"""
        locked_tasks = db.query(ScheduleTask).filter(
            ScheduleTask.batch_id == batch_id,
            ScheduleTask.is_locked == True
        ).all()
        
        locked_ids = [t.id for t in locked_tasks]
        return self.run(db, {
            'products': products_data,
            'locked_task_ids': locked_ids
        })
