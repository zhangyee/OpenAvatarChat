

import os
import re
from typing import Dict, Optional, cast
from loguru import logger
from pydantic import BaseModel, Field
from abc import ABC
from dashscope import Application
from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDataInfo, HandlerDetail
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry


class LLMBailianConfig(HandlerBaseConfigModel, BaseModel):
    app_id: str = Field(default=None)
    api_key: str = Field(default=os.getenv("DASHSCOPE_API_KEY"))
    system_prompt: str = Field(default="请你扮演一个 AI 助手，用简短的对话来回答用户的问题，并在对话内容中加入合适的标点符号，不需要加入标点符号相关的内容")
    enable_video_input: bool = Field(default=False)
    history_length: int = Field(default=20)
    stream: bool = Field(default=True)


class LLMBailianContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config = None
        self.local_session_id = 0
        self.app_id = None
        self.api_key = None
        self.bailian_session_id = None  # 百炼的会话 ID，用于多轮对话
        self.input_texts = ""
        self.output_texts = ""
        self.current_image = None
        self.enable_video_input = False
        self.stream = True


class HandlerLLMBailian(HandlerBase, ABC):
    def __init__(self):
        super().__init__()

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            config_model=LLMBailianConfig,
        )

    def get_handler_detail(self, session_context: SessionContext,
                           context: HandlerContext) -> HandlerDetail:
        definition = DataBundleDefinition()
        definition.add_entry(DataBundleEntry.create_text_entry("avatar_text"))
        inputs = {
            ChatDataType.HUMAN_TEXT: HandlerDataInfo(
                type=ChatDataType.HUMAN_TEXT,
            ),
            ChatDataType.CAMERA_VIDEO: HandlerDataInfo(
                type=ChatDataType.CAMERA_VIDEO,
            ),
        }
        outputs = {
            ChatDataType.AVATAR_TEXT: HandlerDataInfo(
                type=ChatDataType.AVATAR_TEXT,
                definition=definition,
            )
        }
        return HandlerDetail(
            inputs=inputs, outputs=outputs,
        )

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[BaseModel] = None):
        if isinstance(handler_config, LLMBailianConfig):
            if handler_config.api_key is None or len(handler_config.api_key) == 0:
                error_message = 'api_key is required in config/xxx.yaml, when use handler_llm_bailian'
                logger.error(error_message)
                raise ValueError(error_message)
            if handler_config.app_id is None or len(handler_config.app_id) == 0:
                error_message = 'app_id is required in config/xxx.yaml, when use handler_llm_bailian'
                logger.error(error_message)
                raise ValueError(error_message)

    def create_context(self, session_context, handler_config=None):
        if not isinstance(handler_config, LLMBailianConfig):
            handler_config = LLMBailianConfig()
        context = LLMBailianContext(session_context.session_info.session_id)
        context.app_id = handler_config.app_id
        context.api_key = handler_config.api_key
        context.enable_video_input = handler_config.enable_video_input
        context.stream = handler_config.stream
        context.bailian_session_id = None  # 首次调用时为 None，后续会由百炼返回
        return context

    def start_context(self, session_context, handler_context):
        pass

    def handle(self, context: HandlerContext, inputs: ChatData,
               output_definitions: Dict[ChatDataType, HandlerDataInfo]):
        output_definition = output_definitions.get(ChatDataType.AVATAR_TEXT).definition
        context = cast(LLMBailianContext, context)
        text = None

        # 处理视频输入（如果启用）
        if inputs.type == ChatDataType.CAMERA_VIDEO and context.enable_video_input:
            context.current_image = inputs.data.get_main_data()
            return
        elif inputs.type == ChatDataType.HUMAN_TEXT:
            text = inputs.data.get_main_data()
        else:
            return

        speech_id = inputs.data.get_meta("speech_id")
        if (speech_id is None):
            speech_id = context.session_id

        if text is not None:
            context.input_texts += text

        text_end = inputs.data.get_meta("human_text_end", False)
        if not text_end:
            return

        chat_text = context.input_texts
        chat_text = re.sub(r"<\|.*?\|>", "", chat_text)
        if len(chat_text) < 1:
            return

        logger.info(f'bailian app input: app_id={context.app_id}, prompt={chat_text}')

        try:
            # 构建调用参数
            call_params = {
                'api_key': context.api_key,
                'app_id': context.app_id,
                'prompt': chat_text,
                'stream': context.stream
            }

            # 如果有会话 ID，传递以支持多轮对话
            if context.bailian_session_id:
                call_params['session_id'] = context.bailian_session_id
                logger.debug(f'multi-turn conversation, session_id={context.bailian_session_id}')

            # 调用百炼应用 API
            responses = Application.call(**call_params)

            context.current_image = None
            context.input_texts = ''
            context.output_texts = ''

            # 处理流式或非流式响应
            if context.stream:
                # 流式输出（百炼返回的是累积文本，需要计算增量）
                previous_length = 0
                for response in responses:
                    if response.status_code == 200:
                        # 保存会话 ID 用于下次对话
                        if hasattr(response, 'output') and hasattr(response.output, 'session_id'):
                            context.bailian_session_id = response.output.session_id

                        # 输出文本内容
                        if hasattr(response, 'output') and hasattr(response.output, 'text'):
                            current_text = response.output.text
                            if current_text:
                                # 计算增量文本（百炼返回累积文本，只发送新增部分）
                                delta_text = current_text[previous_length:]
                                if delta_text:
                                    context.output_texts = current_text  # 保存完整文本
                                    previous_length = len(current_text)
                                    logger.info(delta_text)  # 只记录增量
                                    output = DataBundle(output_definition)
                                    output.set_main_data(delta_text)  # 只发送增量
                                    output.add_meta("avatar_text_end", False)
                                    output.add_meta("speech_id", speech_id)
                                    yield output
                    else:
                        error_msg = f"Bailian API error: {response.code} - {response.message}"
                        logger.error(error_msg)
                        output = DataBundle(output_definition)
                        output.set_main_data(f"抱歉，服务出现错误：{response.message}")
                        output.add_meta("avatar_text_end", False)
                        output.add_meta("speech_id", speech_id)
                        yield output
                        break
            else:
                # 非流式输出
                if responses.status_code == 200:
                    # 保存会话 ID
                    if hasattr(responses, 'output') and hasattr(responses.output, 'session_id'):
                        context.bailian_session_id = responses.output.session_id

                    # 输出文本内容
                    if hasattr(responses, 'output') and hasattr(responses.output, 'text'):
                        output_text = responses.output.text
                        context.output_texts = output_text
                        logger.info(output_text)
                        output = DataBundle(output_definition)
                        output.set_main_data(output_text)
                        output.add_meta("avatar_text_end", False)
                        output.add_meta("speech_id", speech_id)
                        yield output
                else:
                    error_msg = f"Bailian API error: {responses.code} - {responses.message}"
                    logger.error(error_msg)
                    output = DataBundle(output_definition)
                    output.set_main_data(f"抱歉，服务出现错误：{responses.message}")
                    output.add_meta("avatar_text_end", False)
                    output.add_meta("speech_id", speech_id)
                    yield output

        except Exception as e:
            logger.error(f"Bailian Application API error: {e}")
            output = DataBundle(output_definition)
            output.set_main_data(f"抱歉，调用服务时出现异常：{str(e)}")
            output.add_meta("avatar_text_end", False)
            output.add_meta("speech_id", speech_id)
            yield output

        # 发送结束标记
        context.input_texts = ''
        logger.info('avatar text end')
        end_output = DataBundle(output_definition)
        end_output.set_main_data('')
        end_output.add_meta("avatar_text_end", True)
        end_output.add_meta("speech_id", speech_id)
        yield end_output

    def destroy_context(self, context: HandlerContext):
        pass
