from unittest.mock import patch

from pipecat.frames.frames import TextFrame
from pipecat.processors.aggregators.llm_context import LLMContext

from services.response_filter import ToolStrippingAssistantAggregator


def test_tool_code_stripping():
    # Create dummy context
    context = LLMContext([])

    # Instantiate aggregator
    aggregator = ToolStrippingAssistantAggregator(context)

    # Create TextFrame with tool code block
    content = "```tool_code\ntoolprint(save_contact_name(phone_number='+123', name='John'))\n```\nGreat to meet you, John!"
    text_frame = TextFrame(content)

    # Mock super().process_frame to return [text_frame]
    with patch(
        "pipecat.processors.aggregators.llm_response_universal.LLMAssistantAggregator.process_frame",
        return_value=[text_frame],
    ):
        result = aggregator.process_frame(text_frame, "downstream")

    # Asserts
    assert len(result) == 1
    assert isinstance(result[0], TextFrame)
    assert result[0].text == "Great to meet you, John!"
