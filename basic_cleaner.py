import pandas as pd
import re
import logging

logger = logging.getLogger(__name__)


class JiChuQingXi:
    def __init__(self):
        self.duplicate_count = 0
        self.missing_count = 0

    def clean_all(self, df):
        try:
            if df is None or df.empty:
                logger.warning("数据为空，跳过清洗")
                return df

            logger.info(f"开始基础清洗，原始数据{len(df)}条")

            df = self.remove_missing(df)
            df = self.remove_duplicates(df)
            df = self.clean_spaces(df)
            df = self.remove_special_chars(df)

            logger.info(f"清洗完成，剩余{len(df)}条有效数据")
            return df
        except Exception as e:
            logger.error(f"基础清洗流程失败: {str(e)}", exc_info=True)
            raise

    def remove_missing(self, df):
        try:
            before = len(df)
            df = df.dropna(subset=['content'])
            self.missing_count = before - len(df)
            if self.missing_count > 0:
                logger.warning(f"删除{self.missing_count}条缺失值")
            return df.reset_index(drop=True)
        except KeyError as e:
            logger.error(f"列名错误，找不到content列: {e}")
            raise

    def remove_duplicates(self, df):
        try:
            before = len(df)
            df = df.drop_duplicates(subset=['content'], keep='first')
            self.duplicate_count = before - len(df)
            if self.duplicate_count > 0:
                logger.info(f"去重完成，删除{self.duplicate_count}条重复")
            return df.reset_index(drop=True)
        except Exception as e:
            logger.error(f"去重操作失败: {e}")
            raise

    def clean_spaces(self, df):
        try:
            df['content'] = df['content'].apply(lambda x: re.sub(r'\s+', ' ', str(x).strip()))
            return df
        except Exception as e:
            logger.error(f"空格清洗失败: {e}")
            return df

    def remove_special_chars(self, df):
        try:
            pattern = r'[^\w\s\u4e00-\u9fff.,!?;:\'\"()-]'
            df['content'] = df['content'].apply(lambda x: re.sub(pattern, '', str(x)))
            return df
        except Exception as e:
            logger.error(f"特殊字符清理失败: {e}")
            return df
