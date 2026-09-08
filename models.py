from pydantic import BaseModel

class LoadAverage(BaseModel):
    min_1: float
    min_5: float
    min_15: float

class CpuMetrics(BaseModel):
    temperature: float | None
    usage_percent: float
    load_average: LoadAverage

class RamMetrics(BaseModel):
    total: int
    available: int
    usage: float

class SwapMetrics(BaseModel):
    total: int
    used: int
    free: int
    usage: float

class MemoryMetrics(BaseModel):
    ram: RamMetrics
    swap: SwapMetrics

class PartitionMetrics(BaseModel):
    partition: str
    mountpoint: str
    total: int
    used: int
    free: int
    usage_percent: float

class DiskMetrics(BaseModel):
    temperature: float | None
    partitions: list[PartitionMetrics]

class DockerContainerMetrics(BaseModel):
    status: str
    oom_killed: bool | None
    exit_code: int | None
    error: str | None
    health: str | None

class SystemStatus(BaseModel):
    uptime: float
    cpu: CpuMetrics
    memory: MemoryMetrics
    disks: dict[str, DiskMetrics]
    docker_containers: dict[str, DockerContainerMetrics]