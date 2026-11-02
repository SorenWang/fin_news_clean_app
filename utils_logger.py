import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name='finclean', log_level=logging.INFO):
    try:
        logger = logging.getLogger(name)
        logger.setLevel(log_level)

        if logger.handlers:
            return logger

        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'finclean_{timestamp}.log'

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        logger.info("=" * 50)
        logger.info("金融文本智能清洗工具启动")
        logger.info("=" * 50)

        return logger
    except Exception as e:
        print(f"日志初始化失败: {e}")
        raise


class TongJiXinXi:
    def __init__(self):
        self.total_count = 0
        self.clean_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None

    def start_timer(self):
        from time import time
        self.start_time = time()

    def stop_timer(self):
        from time import time
        self.end_time = time()

    def get_elapsed(self):
        if not self.start_time:
            return 0
        end = self.end_time if self.end_time else self.start_time
        return end - self.start_time

    def generate_report(self):
        try:
            elapsed = self.get_elapsed()
            report = {
                '总处理数': self.total_count,
                '成功清洗数': self.clean_count,
                '失败数': self.error_count,
                '耗时(秒)': round(elapsed, 2),
                '成功率': f"{(self.clean_count / self.total_count * 100) if self.total_count > 0 else 0:.2f}%"
            }
            return report
        except ZeroDivisionError as e:
            logger = logging.getLogger(__name__)
            logger.error(f"统计报告计算错误: {e}")
            return {'error': '统计数据异常'}
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"生成报告失败: {e}")
            return {'error': str(e)}


class ConfigManager:
    def __init__(self):
        self.config = {
            'llm_base_url': 'http://localhost:8080',
            'batch_size': 50,
            'max_retries': 3,
            'timeout': 30
        }

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def save_config(self, filepath):
        import json
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"保存配置失败: {e}")

    def load_config(self, filepath):
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            logger = logging.getLogger(__name__)
            logger.error(f"配置文件格式错误: {e}")
        except FileNotFoundError:
            logger = logging.getLogger(__name__)
            logger.warning(f"配置文件不存在: {filepath}")
