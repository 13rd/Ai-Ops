from dataclasses import dataclass, field

@dataclass
class Profile:
    name: str
    server_id: int
    label: str
    cpu_base: float
    cpu_amplitude: float
    cpu_noise: float
    cpu_burst_prob: float
    cpu_burst_mag: float
    ram_base: float
    ram_amplitude: float
    ram_noise: float
    disk_io_base: float
    disk_io_noise: float
    disk_drift_gb_per_day: float
    disk_total_gb: int
    net_rx_base: float
    net_rx_noise: float
    net_tx_base: float
    net_tx_noise: float
    proc_base: int
    proc_cpu_coeff: float
    proc_noise: int
    conn_base: int
    conn_noise: int
    uptime_hours: float
    load_per_cpu: float
    anomaly_types: list = field(default_factory=list)
    anomaly_schedule_min: list = field(default_factory=list)

PROFILES: dict[str, Profile] = {
    "web_server": Profile(
        name="web_server",
        server_id=10,
        label="Web Server",
        cpu_base=35, cpu_amplitude=15, cpu_noise=5, cpu_burst_prob=0.008, cpu_burst_mag=40,
        ram_base=50, ram_amplitude=8, ram_noise=3,
        disk_io_base=800_000, disk_io_noise=300_000, disk_drift_gb_per_day=0.05, disk_total_gb=100,
        net_rx_base=800_000, net_rx_noise=300_000, net_tx_base=500_000, net_tx_noise=200_000,
        proc_base=160, proc_cpu_coeff=0.8, proc_noise=10,
        conn_base=120, conn_noise=25,
        uptime_hours=720, load_per_cpu=4.0,
        anomaly_types=["cpu_spike", "service_down"],
        anomaly_schedule_min=[45, 160, 290, 410],
    ),
    "database": Profile(
        name="database",
        server_id=11,
        label="Database Server",
        cpu_base=30, cpu_amplitude=10, cpu_noise=4, cpu_burst_prob=0.003, cpu_burst_mag=30,
        ram_base=70, ram_amplitude=10, ram_noise=2,
        disk_io_base=2_000_000, disk_io_noise=500_000, disk_drift_gb_per_day=0.15, disk_total_gb=200,
        net_rx_base=300_000, net_rx_noise=100_000, net_tx_base=600_000, net_tx_noise=200_000,
        proc_base=60, proc_cpu_coeff=0.5, proc_noise=5,
        conn_base=40, conn_noise=10,
        uptime_hours=1440, load_per_cpu=3.0,
        anomaly_types=["memory_leak", "disk_pressure"],
        anomaly_schedule_min=[60, 190, 330, 470],
    ),
    "file_storage": Profile(
        name="file_storage",
        server_id=12,
        label="File Storage",
        cpu_base=10, cpu_amplitude=5, cpu_noise=3, cpu_burst_prob=0.002, cpu_burst_mag=15,
        ram_base=25, ram_amplitude=5, ram_noise=2,
        disk_io_base=3_000_000, disk_io_noise=1_000_000, disk_drift_gb_per_day=0.8, disk_total_gb=500,
        net_rx_base=100_000, net_rx_noise=50_000, net_tx_base=200_000, net_tx_noise=100_000,
        proc_base=25, proc_cpu_coeff=0.3, proc_noise=3,
        conn_base=10, conn_noise=5,
        uptime_hours=2000, load_per_cpu=2.0,
        anomaly_types=["disk_pressure"],
        anomaly_schedule_min=[80, 240, 400],
    ),
    "worker": Profile(
        name="worker",
        server_id=13,
        label="Worker Node",
        cpu_base=8, cpu_amplitude=5, cpu_noise=3, cpu_burst_prob=0.04, cpu_burst_mag=85,
        ram_base=35, ram_amplitude=10, ram_noise=4,
        disk_io_base=300_000, disk_io_noise=200_000, disk_drift_gb_per_day=0.03, disk_total_gb=50,
        net_rx_base=50_000, net_rx_noise=30_000, net_tx_base=80_000, net_tx_noise=40_000,
        proc_base=40, proc_cpu_coeff=1.5, proc_noise=15,
        conn_base=8, conn_noise=4,
        uptime_hours=360, load_per_cpu=5.0,
        anomaly_types=["cpu_spike", "container_crash"],
        anomaly_schedule_min=[35, 130, 250, 380, 500],
    ),
    "monitoring": Profile(
        name="monitoring",
        server_id=14,
        label="Monitoring",
        cpu_base=10, cpu_amplitude=3, cpu_noise=2, cpu_burst_prob=0.001, cpu_burst_mag=10,
        ram_base=22, ram_amplitude=4, ram_noise=2,
        disk_io_base=100_000, disk_io_noise=50_000, disk_drift_gb_per_day=0.1, disk_total_gb=50,
        net_rx_base=150_000, net_rx_noise=60_000, net_tx_base=80_000, net_tx_noise=30_000,
        proc_base=35, proc_cpu_coeff=0.5, proc_noise=3,
        conn_base=20, conn_noise=5,
        uptime_hours=1500, load_per_cpu=1.5,
        anomaly_types=["service_down"],
        anomaly_schedule_min=[50, 180, 320, 460],
    ),
    "load_balancer": Profile(
        name="load_balancer",
        server_id=15,
        label="Load Balancer",
        cpu_base=25, cpu_amplitude=10, cpu_noise=4, cpu_burst_prob=0.005, cpu_burst_mag=25,
        ram_base=40, ram_amplitude=6, ram_noise=3,
        disk_io_base=50_000, disk_io_noise=20_000, disk_drift_gb_per_day=0.01, disk_total_gb=50,
        net_rx_base=2_500_000, net_rx_noise=800_000, net_tx_base=2_000_000, net_tx_noise=600_000,
        proc_base=50, proc_cpu_coeff=0.6, proc_noise=5,
        conn_base=200, conn_noise=40,
        uptime_hours=1000, load_per_cpu=3.5,
        anomaly_types=["network_anomaly", "service_down"],
        anomaly_schedule_min=[40, 150, 280, 420, 550],
    ),
}
