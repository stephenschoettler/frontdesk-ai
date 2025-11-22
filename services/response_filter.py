import re
from typing import List

from pipecat.frames.frames import TextFrame, Frame, BotStoppedSpeakingFrame
from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator


class ToolStrippingAssistantAggregator(LLMAssistantAggregator):
    async def process_frame(self, frame: Frame, direction) -> List[Frame]:
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            cleaned_text = re.sub(r"```tool_code\s*[\s\S]*?```", "", frame.text)
            cleaned_text = cleaned_text.strip()
            if cleaned_text:
                frame.text = cleaned_text
                return [frame]
            else:
                return []
        if isinstance(frame, BotStoppedSpeakingFrame):
            return [frame]
        else:
            return [frame]

    async def push_aggregation(self):
        aggregation = self._aggregation
        self._aggregation = []
        if aggregation:
            self._context.add_messages(
                [
                    {
                        "role": "assistant",
                        "content": " ".join(item.text for item in aggregation),
                    }
                ]
            )
