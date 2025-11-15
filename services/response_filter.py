import re
from typing import List, Any

from pipecat.frames.frames import TextFrame, Frame
from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator


class ToolStrippingAssistantAggregator(LLMAssistantAggregator):
    def process_frame(self, frame: Frame, direction: Any) -> List[Frame]:
        frames = super().process_frame(frame, direction)
        filtered_frames = []
        for f in frames:
            if isinstance(f, TextFrame):
                cleaned_text = re.sub(r"```tool_code\s*[\s\S]*?```", "", f.text)
                cleaned_text = cleaned_text.strip()
                if cleaned_text:
                    f.text = cleaned_text
                    filtered_frames.append(f)
            else:
                filtered_frames.append(f)
        return filtered_frames
