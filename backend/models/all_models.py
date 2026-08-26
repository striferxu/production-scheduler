"""全部数据库模型 - 9大实体 + 关联表"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Table, Text, Time
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


# ========== 关联表 ==========

# 工序-设备 多对多
process_device = Table('process_device', Base.metadata,
    Column('process_id', Integer, ForeignKey('processes.id'), primary_key=True),
    Column('device_id', Integer, ForeignKey('devices.id'), primary_key=True),
)

# 工序-设备组 多对多  
process_device_group = Table('process_device_group', Base.metadata,
    Column('process_id', Integer, ForeignKey('processes.id'), primary_key=True),
    Column('device_group_id', Integer, ForeignKey('device_groups.id'), primary_key=True),
)

# 员工-设备 技能矩阵
employee_device = Table('employee_device', Base.metadata,
    Column('employee_id', Integer, ForeignKey('employees.id'), primary_key=True),
    Column('device_id', Integer, ForeignKey('devices.id'), primary_key=True),
)

# 员工-工序 技能矩阵
employee_process = Table('employee_process', Base.metadata,
    Column('employee_id', Integer, ForeignKey('employees.id'), primary_key=True),
    Column('process_id', Integer, ForeignKey('processes.id'), primary_key=True),
)

# 班次-轮班模式关联
shift_rotation = Table('shift_rotation', Base.metadata,
    Column('rotation_id', Integer, ForeignKey('rotations.id'), primary_key=True),
    Column('shift_id', Integer, ForeignKey('shifts.id'), primary_key=True),
    Column('sequence_order', Integer, default=0),  # 在轮班序列中的顺序
)


# ========== 1. 产品分类 ==========
class ProductCategory(Base):
    __tablename__ = 'product_categories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)
    
    products = relationship('Product', back_populates='category')


# ========== 2. 产品 ==========
class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey('product_categories.id'))
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)
    
    category = relationship('ProductCategory', back_populates='products')
    routes = relationship('ProductRoute', back_populates='product')


# ========== 3. 设备组 ==========
class DeviceGroup(Base):
    __tablename__ = 'device_groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    # 设备组级别工作时间段
    work_start_time = Column(String(5), default='00:00')  # HH:MM
    work_end_time = Column(String(5), default='23:59')
    status = Column(String(20), default='available')  # available/disabled/maintenance
    created_at = Column(DateTime, default=datetime.now)
    
    devices = relationship('Device', back_populates='group')


# ========== 4. 设备 ==========
class Device(Base):
    __tablename__ = 'devices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    group_id = Column(Integer, ForeignKey('device_groups.id'))
    description = Column(String(500))
    # 单台设备级别工作时间段（可覆盖设备组默认值）
    work_start_time = Column(String(5))  # null表示继承设备组
    work_end_time = Column(String(5))
    status = Column(String(20), default='available')  # available/disabled/maintenance
    created_at = Column(DateTime, default=datetime.now)
    
    group = relationship('DeviceGroup', back_populates='devices')


# ========== 5. 工序 ==========
class Process(Base):
    __tablename__ = 'processes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(String(500))
    is_splittable = Column(Boolean, default=True)  # 是否支持并行拆分
    
    devices = relationship('Device', secondary=process_device, backref='processes')
    device_groups = relationship('DeviceGroup', secondary=process_device_group, backref='processes')
    route_steps = relationship('RouteStep', back_populates='process')
    created_at = Column(DateTime, default=datetime.now)


# ========== 6. 工艺路线与工序步骤 ==========
class ProductRoute(Base):
    __tablename__ = 'product_routes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey('products.id'), unique=True, nullable=False)
    name = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)
    
    product = relationship('Product', back_populates='routes')
    steps = relationship('RouteStep', back_populates='route', order_by='RouteStep.step_order')


class RouteStep(Base):
    """工艺路线中的工序步骤"""
    __tablename__ = 'route_steps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey('product_routes.id'), nullable=False)
    process_id = Column(Integer, ForeignKey('processes.id'), nullable=False)
    step_order = Column(Integer, nullable=False)  # 工序顺序
    process_time_per_unit = Column(Float, nullable=False, default=0)  # 单件加工时长（分钟）
    
    route = relationship('ProductRoute', back_populates='steps')
    process = relationship('Process', back_populates='route_steps')


# ========== 7. 人员组别 ==========
class EmployeeGroup(Base):
    __tablename__ = 'employee_groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)
    
    employees = relationship('Employee', back_populates='group')


# ========== 8. 班次 ==========
class Shift(Base):
    __tablename__ = 'shifts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    start_time = Column(String(5), nullable=False)  # HH:MM
    end_time = Column(String(5), nullable=False)      # HH:MM, 支持跨天(end<start)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)


# ========== 轮班模式 ==========
class Rotation(Base):
    __tablename__ = 'rotations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    cycle_days = Column(Integer, default=3)  # 轮班周期天数
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)
    
    shift_rotations = relationship('Shift', secondary=shift_rotation, backref='rotations',
                                  order_by='shift_rotation.c.sequence_order')


# ========== 9. 员工 ==========
class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    group_id = Column(Integer, ForeignKey('employee_groups.id'))
    employee_code = Column(String(50), unique=True)
    # 班次分配
    shift_id = Column(Integer, ForeignKey('shifts.id'), nullable=True)  # 固定班次
    rotation_id = Column(Integer, ForeignKey('rotations.id'), nullable=True)  # 轮班模式
    rotation_start_shift_id = Column(Integer, ForeignKey('shifts.id'), nullable=True)  # 轮班起始班次
    rotation_start_date = Column(String(10), nullable=True)  # 轮班起始日期 YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.now)
    
    group = relationship('EmployeeGroup', back_populates='employees')
    shift = relationship('Shift', foreign_keys=[shift_id])
    rotation = relationship('Rotation', foreign_keys=[rotation_id])
    rotation_start_shift = relationship('Shift', foreign_keys=[rotation_start_shift_id])
    devices = relationship('Device', secondary=employee_device, backref='employees')
    processes = relationship('Process', secondary=employee_process, backref='employees')


# ========== 排程结果表 ==========
class ScheduleTask(Base):
    """排程任务结果"""
    __tablename__ = 'schedule_tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(50), index=True)  # 批次ID，同一次排程共享
    product_id = Column(Integer, ForeignKey('products.id'))
    product_name = Column(String(200))
    product_category = Column(String(100))
    route_step_id = Column(Integer, ForeignKey('route_steps.id'))
    process_id = Column(Integer, ForeignKey('processes.id'))
    process_name = Column(String(200))
    step_order = Column(Integer)
    device_id = Column(Integer, ForeignKey('devices.id'))
    device_name = Column(String(100))
    device_group_name = Column(String(100))
    employee_id = Column(Integer, ForeignKey('employees.id'))
    employee_name = Column(String(100))
    employee_group_name = Column(String(100))
    shift_name = Column(String(100))
    quantity = Column(Float, default=0)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)
    due_date = Column(DateTime)
    is_locked = Column(Boolean, default=False)  # 是否被手动锁定
    created_at = Column(DateTime, default=datetime.now)


# ========== 用户表 ==========
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default='user')  # admin / user
    created_at = Column(DateTime, default=datetime.now)


# ========== 备份记录 ==========
class BackupRecord(Base):
    __tablename__ = 'backup_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(500))
    backup_type = Column(String(20))  # auto / manual
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
