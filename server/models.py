from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
YesNoSkip = Literal["yes", "no", "skip"]

class StartRequest(BaseModel):
    theme: str = Field(..., description="Theme key")
    difficulty: Difficulty = Field("easy")

class AnswerRequest(BaseModel):
    question_key: str
    answer: YesNoSkip

class GuessFeedbackRequest(BaseModel):
    guess_id: str
    correct: bool

class ApiQuestion(BaseModel):
    key: str
    text: str

class ApiGuess(BaseModel):
    id: str
    label: str
    confidence: float

class ApiDone(BaseModel):
    message: str

class ApiTurnResponse(BaseModel):
    game_id: str
    action: Dict[str, Any]
    question: Optional[ApiQuestion] = None
    guess: Optional[ApiGuess] = None
    done: Optional[ApiDone] = None
    candidates_left: int
    step: int
    asked_count: int
    theme: str
    difficulty: Difficulty

class MetaResponse(BaseModel):
    themes: List[Dict[str, Any]]
    difficulties: List[str]
    items_count: int
    features_count: int

class WordsResponse(BaseModel):
    theme: str
    difficulty: Difficulty
    words: List[Dict[str, Any]]
