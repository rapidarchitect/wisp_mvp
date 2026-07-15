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
  LinearProgress,
  Radio,
  RadioGroup,
  Step,
  StepLabel,
  Stepper,
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
  const [currentStep, setCurrentStep] = useState(0);

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

  const questions = progress.questions;
  const total = questions.length;
  const q = questions[currentStep];
  const progressValue = total === 0 ? 0 : ((currentStep + 1) / total) * 100;
  const canAnswer = progress.status === "assigned" || progress.status === "in_progress";

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {progress.name} ({progress.code})
      </Typography>
      <Chip label={progress.status} sx={{ mb: 2 }} />

      <LinearProgress
        variant="determinate"
        value={progressValue}
        sx={{ mb: 2 }}
        data-testid="question-progress"
      />

      <Stepper activeStep={currentStep} alternativeLabel sx={{ mb: 3 }} data-testid="question-stepper">
        {questions.map((step) => (
          <Step key={step.id}>
            <StepLabel>{step.position}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }} data-testid="step-indicator">
        Question {currentStep + 1} of {total}
      </Typography>

      {q && (
        <Card key={q.id} data-question={q.id} sx={{ mb: 2 }} data-testid={`question-card-${q.id}`}>
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
                          disabled={!canAnswer}
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
                  disabled={loading || !canAnswer}
                  sx={{ mt: 1 }}
                >
                  Skip
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
        <Button
          variant="outlined"
          disabled={currentStep === 0}
          onClick={() => setCurrentStep((s) => s - 1)}
          data-testid="prev-step"
        >
          Previous
        </Button>
        <Button
          variant="outlined"
          disabled={currentStep === total - 1}
          onClick={() => setCurrentStep((s) => s + 1)}
          data-testid="next-step"
        >
          Next
        </Button>
      </Box>

      {currentStep === total - 1 && (
        <Card variant="outlined" sx={{ mb: 2 }} data-testid="questionnaire-summary">
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Summary
            </Typography>
            {questions.map((sq) => (
              <Box key={sq.id} sx={{ mb: 1 }}>
                <Typography variant="body2" fontWeight="bold">
                  {sq.position}. {sq.text}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {sq.answer
                    ? sq.answer.skipped
                      ? "Skipped"
                      : `Answer: ${sq.answer.value}`
                    : "Not answered"}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

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

      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
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
        {canAnswer && (
          <Button
            variant="outlined"
            onClick={answerAll}
            disabled={loading}
            data-testid="answer-all"
          >
            Answer all remaining questions
          </Button>
        )}
      </Box>
    </Box>
  );
}
