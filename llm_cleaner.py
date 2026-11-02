import requests
import json
import re
import logging
import time

logger = logging.getLogger(__name__)

# 常见 LLM 特殊 token 模式（仅匹配 token 本身，不匹配内容）
_SPECIAL_TOKEN_PATTERNS = [
    r'<\|im_start\|>\w+\n?',             # ChatML 角色起始（如 <|im_start|>user）
    r'<\|im_end\|>\n?',                  # ChatML 结束
    r'<\|assistant\|>',                  # ChatML 角色标签（孤立出现）
    r'<\|user\|>',
    r'<\|system\|>',
    r'<\|endoftext\|>',
    r'<\|begin_of_text\|>',
    r'<\|end_of_text\|>',
    r'<\|start_header_id\|>\w+<\|end_header_id\|>',  # Llama 3 header
    r'<\|eot_id\|>',
    r'</s>',                             # LLaMA stop token
    r'<s>',                              # LLaMA start token
    r'\[INST\]',                         # Mistral/Llama2 指令标记（不匹配中间的指令内容）
    r'\[/INST\]',
    r'<<SYS>>',                          # Llama2 系统提示标记
    r'<</SYS>>',
    r'<\|python_tag\|>',
    r'<\|vision_start\|>',
    r'<\|vision_end\|>',
    r'<\|reserved_special_token_\d+>',
    r'<\|unused\d+>',
]

# 常见的 markdown / 格式标记（同样只匹配标记本身）
_FORMAT_PATTERNS = [
    (r'```[\w]*\n?', ''),          # 代码块开始标记
    (r'^```\s*$', '', re.MULTILINE),  # 代码块结束标记（单独成行）
    (r'\*\*(.*?)\*\*', r'\1'),     # 粗体
    (r'\*(.*?)\*', r'\1'),         # 斜体
    (r'^#{1,6}\s+', '', re.MULTILINE),  # 标题标记
    (r'^[-*+]\s+', '', re.MULTILINE),   # 无序列表标记
    (r'^\d+\.\s+', '', re.MULTILINE),   # 有序列表标记
]


class DaMoXingQingXi:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30
        self.retry_count = 3

    def clean_with_llm(self, text_list):
        """对文本列表逐一调用 LLM 进行智能清洗"""
        try:
            if not text_list:
                logger.warning("输入文本列表为空")
                return []

            logger.info(f"开始LLM清洗，共{len(text_list)}条文本")
            cleaned = []

            for idx, text in enumerate(text_list):
                result = self._call_llm_api(text, idx)
                if result:
                    cleaned.append(result)
                else:
                    logger.warning(f"第{idx}条LLM清洗失败，保留原文")
                    cleaned.append(text)

                if (idx + 1) % 10 == 0:
                    logger.info(f"已处理{idx + 1}/{len(text_list)}条")

            logger.info(f"LLM清洗完成，成功{len(cleaned)}条")
            return cleaned
        except Exception as e:
            logger.error(f"LLM清洗流程失败: {str(e)}", exc_info=True)
            raise

    def _call_llm_api(self, text, idx):
        """调用 llama-server /completion 接口"""
        for attempt in range(self.retry_count):
            try:
                prompt = self._build_prompt(text)

                payload = {
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 512,
                    "stop": [
                        "</s>",
                        "<|im_end|>",
                        "<|endoftext|>",
                        "<|eot_id|>",
                        "\n\n\n",
                    ],
                    "repeat_penalty": 1.1,
                }

                response = requests.post(
                    f"{self.base_url}/completion",
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    logger.warning(f"LLM返回状态码{response.status_code}，尝试 {attempt + 1}/{self.retry_count}")
                    if attempt < self.retry_count - 1:
                        time.sleep(2)
                    continue

                result_json = response.json()
                raw_content = result_json.get('content', '')

                if not raw_content:
                    logger.warning(f"第{idx}条LLM返回空结果")
                    if attempt < self.retry_count - 1:
                        time.sleep(1)
                    continue

                # 多层清洗提取最终文本
                cleaned_text = self._extract_clean_text(raw_content, text)

                if not cleaned_text or len(cleaned_text) < 2:
                    logger.warning(f"第{idx}条清洗后文本过短，保留原文")
                    return text

                return cleaned_text

            except requests.exceptions.ConnectionError as e:
                logger.error(f"无法连接到LLM服务({attempt + 1}/{self.retry_count}): {e}")
                time.sleep(2)
            except json.JSONDecodeError as e:
                logger.error(f"LLM响应JSON解析失败: {e}")
                return None
            except requests.exceptions.Timeout as e:
                logger.warning(f"LLM请求超时({attempt + 1}/{self.retry_count})")
                time.sleep(1)
            except Exception as e:
                logger.error(f"LLM调用异常: {e}")
                return None

        logger.error(f"第{idx}条重试{self.retry_count}次后仍失败")
        return None

    def _build_prompt(self, text):
        """构建清洗提示词——严格约束输出格式，禁止生成分析报告"""
        prompt = f"""你是一个金融文本清洗工具。你的唯一任务是输出清洗后的纯文本，禁止写分析报告、禁止评价、禁止总结。

输入文本：{text}

规则：
- 修正错别字和语法错误
- 保持金融术语不变
- 删除无意义符号和乱码
- 保持原意，不增删事实信息
- 如果没有任何需要修改的地方，原样输出输入文本
- 禁止输出"分析""点评""总结""建议"等内容

输出格式（严格遵守，只输出下面两个字段，不要输出任何其他内容）：
[清洗后]
这里写清洗后的纯文本
[说明]
这里写做了哪些修改（若未修改则写"无修改"）"""
        return prompt

    # 分析报告特征词——如果输出中包含这些，说明模型写了分析报告而非纯清洗结果
    _ANALYSIS_PATTERNS = [
        r'这段文本',
        r'原文.*问题',
        r'可以看出[，,]',
        r'综上',
        r'建议[：:]',
        r'点评[：:]',
        r'总结[：:]',
        r'分析[：:]',
        r'评价[：:]',
    ]

    def _extract_clean_text(self, raw_output, original_text):
        """
        从 LLM 原始输出中提取清洗后的纯文本。
        优先按新的 [清洗后]/[说明] 格式解析，若失败则回退到旧格式提取。
        """
        text = raw_output

        # ===== 第1步：去除所有 LLM 特殊 token =====
        for pattern in _SPECIAL_TOKEN_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.DOTALL)

        # ===== 第2步：按新格式提取 [清洗后] 和 [说明] =====
        note = ''
        pattern_new = r'\[清洗后\]\s*\n?(.*?)(?:\[说明\]\s*\n?(.*?))?$'
        m = re.search(pattern_new, text, re.DOTALL)
        if m:
            body = m.group(1).strip()
            if m.group(2):
                note = m.group(2).strip()
            if body and len(body) >= 2:
                body = self._final_clean(body)
                if note:
                    body = f"{body}（修改说明：{note}）"
                return body

        # ===== 第3步（回退）：按旧标记提取 =====
        markers = [
            '清洗结果：', '清洗结果:', '清洗后的文本：', '清洗后文本：',
            '输出：', '结果：',
        ]
        extracted = text
        for marker in markers:
            if marker in text:
                parts = text.rsplit(marker, 1)
                extracted = parts[-1].strip()
                break

        # 如果模型回显了原始文本，取后半段
        if original_text in extracted:
            after_original = extracted.rsplit(original_text, 1)[-1].strip()
            if len(after_original) > 5:
                extracted = after_original

        # ===== 第4步：去除分析报告风格的段落 =====
        extracted = self._strip_analysis(extracted)

        # ===== 第5步：格式清理 =====
        extracted = self._final_clean(extracted)

        return extracted

    def _strip_analysis(self, text):
        """检测并移除分析报告风格的句子/段落。
        如果文本整体就是分析报告（包含大量分析特征词且字数远多于原文），返回空字符串以触发回退。
        """
        # 按行处理，过滤分析特征行
        lines = text.splitlines()
        kept = []
        for line in lines:
            is_analysis = False
            for pat in self._ANALYSIS_PATTERNS:
                if re.search(pat, line):
                    is_analysis = True
                    break
            # 过滤以分析动词开头的行
            if re.match(r'^(这段|原文|上述|该文|从这|综上|总体|整体|总的)', line):
                is_analysis = True
            if not is_analysis:
                kept.append(line)
        return '\n'.join(kept)

    def _final_clean(self, text):
        """最终格式清理：去除 markdown 标记 → 压缩空白 → 修剪"""
        for pattern, replacement, *flags in _FORMAT_PATTERNS:
            flag = flags[0] if flags else 0
            text = re.sub(pattern, replacement, text, flags=flag)

        text = re.sub(r'[#\*\-=\+~`@\$%\^&]{3,}', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = '\n'.join(line.strip() for line in text.splitlines())
        text = text.strip()
        text = re.sub(r'^[,，。；;:：、\s]+', '', text)
        return text

    def check_service_status(self):
        """检查 llama-server 是否在线"""
        endpoints = [
            f"{self.base_url}/health",
            f"{self.base_url}/v1/models",
            f"{self.base_url}/",
        ]
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    logger.info(f"LLM服务连接成功: {endpoint}")
                    return True
            except Exception:
                continue

        logger.error(f"LLM服务健康检查失败: 无法连接到 {self.base_url}")
        return False
