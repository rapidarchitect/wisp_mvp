import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

type Assignment = {
  code: string;
  name: string;
  status: string;
};

const statusOrder: Record<string, number> = {
  pending_questions: 0,
  assigned: 1,
  in_progress: 2,
  in_review: 3,
  approved: 4,
};

const statusColor: Record<string, "default" | "primary" | "warning" | "success" | "info"> = {
  pending_questions: "default",
  assigned: "info",
  in_progress: "primary",
  in_review: "warning",
  approved: "success",
};

export function DashboardPage() {
  const { state } = useAuth();
  const user = state.status === "authenticated" ? state.user : null;
  const navigate = useNavigate();

  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    apiFetch<Assignment[]>("/domains/assigned")
      .then(setAssignments)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load assignments"),
      );
  }, [user]);

  const sorted = useMemo(
    () =>
      (assignments ?? []).slice().sort((a, b) => {
        const ao = statusOrder[a.status] ?? 99;
        const bo = statusOrder[b.status] ?? 99;
        if (ao !== bo) return ao - bo;
        return a.name.localeCompare(b.name);
      }),
    [assignments],
  );

  const isAdmin = user?.roles.includes("admin");
  const isContributor = user?.roles.includes("contributor");
  const isReviewer = user?.roles.includes("reviewer");

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      {user && (
        <Typography variant="body1" sx={{ mb: 3 }}>
          Welcome, {user.email}. Roles: {user.roles.join(", ")}.
        </Typography>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {assignments === null && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {assignments !== null && sorted.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No domain assignments yet.
          {isAdmin && " Use the Domains page to assign contributors and reviewers."}
        </Alert>
      )}
      {assignments !== null && (
        <>
          <Box sx={{ mb: 3 }}>
            {isReviewer && (
              <Button
                variant="contained"
                onClick={() => navigate("/review")}
                data-testid="dashboard-review-queue-cta"
              >
                Go to review queue
              </Button>
            )}
            {isContributor && !isReviewer && (
              <Button
                variant="contained"
                onClick={() => navigate("/domains")}
                data-testid="dashboard-my-domains-cta"
              >
                My domains
              </Button>
            )}
            {isAdmin && !isReviewer && !isContributor && (
              <Button
                variant="contained"
                onClick={() => navigate("/admin/domains")}
                data-testid="dashboard-admin-domains-cta"
              >
                Manage domains
              </Button>
            )}
          </Box>
          <Grid container spacing={2}>
            {sorted.map((a) => (
              <Grid item xs={12} sm={6} md={4} key={a.code}>
                <Card variant="outlined" data-domain-code={a.code} data-testid={`dashboard-card-${a.code}`}>
                  <CardContent>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography variant="h6">
                        {a.name} ({a.code})
                      </Typography>
                      <Chip label={a.status.replace(/_/g, " ")} color={statusColor[a.status] ?? "default"} size="small" />
                    </Box>
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      onClick={() =>
                        navigate(
                          isReviewer
                            ? `/review/${a.code}`
                            : isContributor
                              ? `/domains/${a.code}`
                              : "/admin/domains",
                        )
                      }
                    >
                      Open
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Box>
  );
}
