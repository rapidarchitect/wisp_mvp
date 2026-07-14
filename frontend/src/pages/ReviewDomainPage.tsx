import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  TextField,
  Typography,
  Alert,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

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

export function ReviewDomainPage() {
  const { code } = useParams<{ code: string }>();
  const { state } = useAuth();
  const user = state.status === "authenticated" ? state.user : null;

  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revisionPrompt, setRevisionPrompt] = useState("");
  const [success, setSuccess] = useState<string | null>(null);
  const [selfReviewWarning, setSelfReviewWarning] = useState(false);

  const loadProgress = () => {
    if (!code) return;
    apiFetch<Progress>(`/domains/${code}/progress`)
      .then((p) => {
        setProgress(p);
        setError(null);
        if (user && p.questions.some((q) => q.answer && q.answer.id === user.id)) {
          setSelfReviewWarning(true);
        }
      })
      .catch((err) =>
        setError(
          err instanceof ApiResponseError ? err.error.message : "Failed to load progress",
        ),
      );
  };

  useEffect(() => {
    loadProgress();
  }, [code]);

  const approve = async () => {
    if (!code) return;
    setLoading(true);
    try {
      const result = (await apiFetch(`/domains/${code}/approve`, {
        method: "POST",
      })) as { self_review_warning?: boolean };
      setSuccess("Domain approved.");
      if (result.self_review_warning) {
        setSelfReviewWarning(true);
      }
      loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to approve domain",
      );
    } finally {
      setLoading(false);
    }
  };

  const defer = async () => {
    if (!code) return;
    setLoading(true);
    try {
      await apiFetch(`/domains/${code}/defer`, { method: "POST" });
      setSuccess("Domain deferred back to contributor.");
      loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to defer domain",
      );
    } finally {
      setLoading(false);
    }
  };

  const revise = async () => {
    if (!code || !revisionPrompt.trim()) return;
    setLoading(true);
    try {
      await apiFetch(`/domains/${code}/revise`, {
        method: "POST",
        body: { revision_prompt: revisionPrompt },
      });
      setSuccess("Domain revised and approved.");
      setRevisionPrompt("");
      loadProgress();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to revise domain",
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

  const compiledAnswer = progress.questions
    .map((q) => q.answer)
    .filter(Boolean)
    .flatMap((a) => a!.followups)
    .some((f) => f.response_text);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Review {progress.name} ({progress.code})
      </Typography>
      <Chip label={progress.status} sx={{ mb: 2 }} />

      {selfReviewWarning && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          You are also the contributor for this domain. Self-review is allowed but flagged.
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Compiled narrative
          </Typography>
          {compiledAnswer ? (
            <Typography whiteSpace="pre-wrap">
              {progress.questions
                .map((q) => `${q.position}. ${q.text}\nAnswer: ${q.answer?.value || "skipped"}`)
                .join("\n\n")}
            </Typography>
          ) : (
            <Typography color="text.secondary">
              Narrative will appear here once the compiled answer is available.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Divider sx={{ my: 2 }} />

      <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
        <Button
          variant="contained"
          color="success"
          onClick={approve}
          disabled={loading || progress.status !== "in_review"}
        >
          Approve
        </Button>
        <Button
          variant="outlined"
          color="warning"
          onClick={defer}
          disabled={loading || progress.status !== "in_review"}
        >
          Defer
        </Button>
      </Box>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            AI revision
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Revision prompt"
            value={revisionPrompt}
            onChange={(e) => setRevisionPrompt(e.target.value)}
            disabled={loading || progress.status !== "in_review"}
          />
          <Button
            variant="contained"
            onClick={revise}
            disabled={loading || !revisionPrompt.trim() || progress.status !== "in_review"}
            sx={{ mt: 2 }}
          >
            Revise and approve
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
