"""Write the video plan (narration, on-screen cards, Shorts, metadata) with Claude."""
import json
from typing import List, Literal

import anthropic
from pydantic import BaseModel, Field


class Card(BaseModel):
    kind: Literal["title", "steps", "chat", "code", "tip", "warning", "recap", "text"]
    heading: str = Field(description="Short heading, max 6 words")
    lines: List[str] = Field(
        description="2-5 short lines shown on screen. For kind=chat, prefix each line with "
        "'You: ' or 'AI: '. For kind=code, each line is one formula or command."
    )


class Scene(BaseModel):
    voiceover: str = Field(description="Narration for this scene, 1-4 sentences")
    card: Card
    chapter: str = Field(default="", description="Short YouTube chapter name if this scene starts a "
                         "new section of the video (intro, each step, tips, recap), otherwise empty")


class Short(BaseModel):
    title: str = Field(description="Shorts title under 60 characters, no hashtags")
    hook: str = Field(description="First line, grabs attention in 2 seconds")
    scenes: List[Scene] = Field(description="3-5 scenes, total under 45 seconds of narration")


class VideoPlan(BaseModel):
    title: str = Field(description="Final YouTube title under 60 characters")
    title_options: List[str]
    thumbnail_words: str = Field(description="2-4 punchy words for the thumbnail, e.g. 'AI WRITES IT'")
    thumbnail_tool: str = Field(description="Main tool name for the thumbnail badge, 1-2 words")
    description_intro: str = Field(description="2 sentences on what the viewer will learn")
    prompts_used: List[str] = Field(description="Every prompt shown in the video, copied out for the description")
    tags: List[str] = Field(description="8-15 search tags")
    scenes: List[Scene] = Field(description="12-20 scenes making up the full tutorial")
    shorts: List[Short]
    fact_check: List[str] = Field(
        description="Specific claims or features the human reviewer must double-check before publishing"
    )


PROMPT = """Write a YouTube tutorial for a faceless channel called {channel}.

Topic: {topic}
Tools: {tools}
Audience: busy office workers in the US and UK, not technical.
Next week's topic (name it in the call to subscribe): {next_topic}

The video has no screen recording: the viewer sees one designed card per scene (a heading
and 2-5 short lines) while an AI voice reads the narration. So make every card carry the
real substance: the exact prompt to type (kind=chat, "You:" / "AI:" lines), the exact
formula or setting (kind=code), numbered steps (kind=steps), a tip or a warning.

Structure: open with the result in the first 15 seconds (kind=title for scene 1), then 4 to
6 numbered steps, 3 tips, one honest warning about limits, a recap, and the call to
subscribe. About {words} words of narration in total. Plain, friendly language, short
sentences, no hype words, never "in today's video". Say "the description" for links.

Accuracy matters more than anything: only describe features of these tools that you are
confident exist today, keep examples generic enough to stay true across versions, and list
anything a reviewer should verify in fact_check.

Also cut {shorts} Shorts: standalone moments (the single best tip, a before/after, one
mistake to avoid), each with a strong hook and under 45 seconds."""


def write_plan(topic: dict, next_topic: str, cfg: dict) -> VideoPlan:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = client.messages.parse(
        model=cfg["script"]["model"],
        max_tokens=16000,
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": PROMPT.format(
                channel=cfg["channel"]["name"],
                topic=topic["title"],
                tools=topic["tools"],
                next_topic=next_topic or "another time-saving AI tool",
                words=cfg["script"]["target_words"],
                shorts=cfg["weekly"]["shorts_per_video"],
            ),
        }],
        output_format=VideoPlan,
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise RuntimeError(f"Script generation stopped early: {response.stop_reason}")
    return response.parsed_output


def load_plan(path) -> VideoPlan:
    return VideoPlan.model_validate(json.loads(open(path).read()))
