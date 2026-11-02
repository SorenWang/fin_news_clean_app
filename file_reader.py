import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WenJianDuQu:
    def __init__(self):
        self.support_ext = ['.csv', '.txt', '.xlsx']

    def read_file(self, file_path):
        try:
            p = Path(file_path)
            if not p.exists():
                logger.error(f"文件不存在: {file_path}")
                raise FileNotFoundError(f"找不到文件: {file_path}")

            ext = p.suffix.lower()
            if ext not in self.support_ext:
                logger.warning(f"不支持的文件格式: {ext}")
                return None

            if ext == '.csv':
                return self._read_csv(p)
            elif ext == '.txt':
                return self._read_txt(p)
            elif ext == '.xlsx':
                return self._read_excel(p)
        except Exception as e:
            logger.error(f"读取文件失败: {str(e)}", exc_info=True)
            raise

    def _normalize_to_content(self, df, source_name):
        """将任意 DataFrame 统一转换为仅含字符串 'content' 列的格式"""
        if df is None or df.empty:
            logger.warning(f"{source_name} 数据为空")
            return df

        # 如果已经有 content 列（大小写不敏感），直接使用
        for col in df.columns:
            if str(col).strip().lower() == 'content':
                df['content'] = df[col].astype(str).str.strip()
                df = df[['content']]
                logger.info(f"{source_name}: 使用已有 'content' 列")
                return df

        # 否则：尝试找到文本列，或者把所有列拼接为 content
        text_cols = []
        for col in df.columns:
            # 检查该列是否主要为字符串类型
            sample = df[col].dropna().head(10)
            if len(sample) > 0:
                try:
                    sample.str  # 测试是否可当字符串处理
                    text_cols.append(col)
                except AttributeError:
                    continue

        if text_cols:
            # 将所有文本列拼接成 content
            logger.info(f"{source_name}: 将 {len(text_cols)} 个文本列拼接为 'content'（{text_cols}）")
            df['content'] = df[text_cols].astype(str).agg(' '.join, axis=1).str.strip()
        else:
            # 没有明显的文本列，把所有列都转字符串拼接
            logger.info(f"{source_name}: 未检测到文本列，将所有列拼接为 'content'")
            df['content'] = df.astype(str).agg(' '.join, axis=1).str.strip()

        # 清除 NaN 被转为字符串 "nan" 的情况
        df['content'] = df['content'].str.replace(r'\bnan\b', '', regex=True).str.strip()
        # 去除多余空格导致的空内容
        df['content'] = df['content'].str.replace(r'\s{2,}', ' ', regex=True)

        df = df[['content']]
        logger.info(f"{source_name}: 归一化完成，共 {len(df)} 条")
        return df

    def _read_csv(self, p):
        try:
            df = pd.read_csv(p, encoding='utf-8')
            logger.info(f"成功读取CSV文件，共{len(df)}条记录")
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(p, encoding='gbk')
                logger.info("使用GBK编码读取成功")
            except Exception as e:
                logger.error(f"CSV编码解析失败: {e}")
                raise
        return self._normalize_to_content(df, f"CSV({p.name})")

    def _read_txt(self, p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            data = [{'content': line.strip()} for line in lines if line.strip()]
            df = pd.DataFrame(data)
            logger.info(f"读取TXT文件，共{len(df)}条文本")
            return df
        except Exception as e:
            logger.error(f"TXT读取异常: {e}")
            raise

    def _read_excel(self, p):
        try:
            df = pd.read_excel(p)
            logger.info(f"读取Excel成功，共{len(df)}条")
        except Exception as e:
            logger.error(f"Excel读取失败: {e}")
            raise
        return self._normalize_to_content(df, f"Excel({p.name})")
