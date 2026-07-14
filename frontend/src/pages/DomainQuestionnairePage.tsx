import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";

type FollowUp = {
  id: number;
  text: string;
  response_text: string | null;
};

type Answer = {
  id: number;
  value: string;
  skipped: number;
  followups_state: string;
  followups: FollowUp[];
};

type Question = {
  id: number;
  text: string;
  position: number;
  answer: Answer | null;
};

type Progress = {
  domain_id: number;
  code: string;
  name: string;
  status: string;
  questions: Question[];
  submit_ready: boolean;
};

export function DomainQuestionnairePage() {
  const { code } = useParams<{ code: string }>();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);

  const loadProgress = async () => {
    if (!code) return;
    try {
      const p = await apiFetch<Progress>(`/domains/${code}/progress`);
      setProgress(p);
      if (!narrative) {
        setNarrative(null);
      }
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to load progress",
      );
    }
  };

  useEffect(() => {
    loadProgress();
  }, [code]);

  const answerQuestion = async (questionId: number, value: string) => {
    setLoading(true);
    try {
      await apiFetch(`/questions/${questionId}/answer`, {
        method: "POST",
        body: { value, skipped: false },
      });
      await loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to save answer",
      );
    } finally {
      setLoading(false);
    }
  };

  const skipQuestion = async (questionId: number) => {
    setLoading(true);
    try {
      await apiFetch(`/questions/${questionId}/answer`, {
        method: "POST",
        body: { skipped: true },
      });
      await loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to skip question",
      );
    } finally {
      setLoading(false);
    }
  };

  const respondFollowup = async (followupId: number, responseText: string) => {
    setLoading(true);
    try {
      await apiFetch(`/followups/${followupId}/respond`, {
        method: "POST",
        body: { response_text: responseText },
      });
      await loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to save follow-up",
      );
    } finally {
      setLoading(false);
    }
  };

  const answerAll = async () => {
    if (!progress) return;
    setLoading(true);
    try {
      for (const q of progress.questions) {
        if (!q.answer) {
          await apiFetch(`/questions/${q.id}/answer`, {
            method: "POST",
            body: { value: "yes", skipped: false },
          });
        }
      }
      const fresh = await apiFetch<Progress>(`/domains/${code}/progress`);
      setProgress(fresh);
      for (const q of fresh.questions) {
        if (q.answer && !q.answer.skipped && q.answer.followups) {
          for (const f of q.answer.followups) {
            if (!f.response_text) {
              await apiFetch(`/followups/${f.id}/respond`, {
                method: "POST",
                body: { response_text: "Documented in policy." },
              });
            }
          }
        }
      }
      await loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to answer questions",
      );
    } finally {
      setLoading(false);
    }
  };

  const compile = async () => {
    if (!code) return;
    setLoading(true);
    try {
      const result = await apiFetch<{ narrative_text: string }>(`/domains/${code}/compile`, {
        method: "POST",
      });
      setNarrative(result.narrative_text);
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to compile domain",
      );
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    if (!code) return;
    setLoading(true);
    try {
      await apiFetch(`/domains/${code}/submit`, { method: "POST" });
      await loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to submit domain",
      );
    } finally {
      setLoading(false);
    }
  };

  if (error) {
    return (
      <Box>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  if (!progress) {
    return <CircularProgress />;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {progress.name} ({progress.code})
      </Typography>
      <Chip label={progress.status} sx={{ mb: 2 }} />

      {progress.questions.map((q) => (
        <Card key={q.id} data-question={q.id} sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {q.position}. {q.text}
            </Typography>
            {q.answer ? (
              <Box data-answered="true">
                {q.answer.skipped ? (
                  <Chip label="Skipped" color="warning" />
                ) : (
                  <>
                    <Typography>Answer: {q.answer.value}</Typography>
                    <Chip
                      label={`Follow-ups: ${q.answer.followups_state}`}
                      sx={{ mt: 1 }}
                    />
                    {q.answer.followups.map((f) => (
                      <Box key={f.id} data-followup={f.id} sx={{ mt: 2 }}>
                        <Typography variant="subtitle2">{f.text}</Typography>
                        <TextField
                          fullWidth
                          label="Response"
                          value={f.response_text || ""}
                          onBlur={(e) =>
                            respondFollowup(f.id, e.target.value)
                          }
                          disabled={progress.status !== "assigned" && progress.status !== "in_progress"}
                        />
                      </Box>
                    ))}
                  </>
                )}
              </Box>
            ) : (
              <>
                <FormControl component="fieldset" fullWidth data-testid={`question-${q.id}-choices`}>
                  <RadioGroup
                    row
                    name={`question-${q.id}`}
                    value=""
                    onChange={(e) => answerQuestion(q.id, e.target.value)}
                  >
                    <FormControlLabel
                      value="yes"
                      control={<Radio />}
                      label={<span data-choice="yes">Yes</span>}
                    />
                    <FormControlLabel
                      value="no"
                      control={<Radio />}
                      label={<span data-choice="no">No</span>}
                    />
                  </RadioGroup>
                </FormControl>
                <Button
                  variant="outlined"
                  color="warning"
                  onClick={() => skipQuestion(q.id)}
                  disabled={loading}
                  sx={{ mt: 1 }}
                >
                  Skip
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      ))}

      {narrative && (
        <Card sx={{ mb: 2 }} data-testid="compiled-narrative">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Compiled narrative
            </Typography>
            <Typography whiteSpace="pre-wrap">{narrative}</Typography>
          </CardContent>
        </Card>
      )}

      <Divider sx={{ my: 2 }} />

      <Box sx={{ display: "flex", gap: 2 }}>
        <Button
          variant="contained"
          onClick={compile}
          disabled={loading || !progress.submit_ready}
        >
          Compile
        </Button>
        <Button
          variant="contained"
          color="success"
          onClick={submit}
          disabled={loading || !narrative}
        >
          Submit for review
        </Button>
        {progress.status === "assigned" || progress.status === "in_progress" ? (
          <Button
            variant="outlined"
            onClick={answerAll}
            disabled={loading}
            data-testid="answer-all"
          >
            Answer all remaining questions
          </Button>
        ) : null}
      </Box>
    </Box>
  );
}
