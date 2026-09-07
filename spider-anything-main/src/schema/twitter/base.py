import typing as t

from pydantic import BaseModel


EntryType = t.Literal["TimelineTimelineModule", "TimelineTimelineItem"]
InstructionType = t.Literal["TimelineAddEntries", "TimelineClearCache"]


class EntryContent(BaseModel):
    entryType: EntryType
    __typename: EntryType
    clientEventInfo: dict


class TimelineItem(EntryContent):
    itemContent: t.Any


class EntryContentItemContent(BaseModel):
    itemType: str
    __typename: str


class TweetWithVisibilityResults(BaseModel):
    result: t.Any


class TimelineTweet(EntryContentItemContent):
    tweet_results: TweetWithVisibilityResults
    tweetDisplayType: t.Optional[str] = None


class Entry(BaseModel):
    entryId: str
    sortIndex: str
    content: EntryContent


class Instruction(BaseModel):
    type: InstructionType
    entries: t.Optional[t.List[Entry]] = None