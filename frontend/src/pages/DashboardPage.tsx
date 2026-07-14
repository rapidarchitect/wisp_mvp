import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

type Assignment = {
  code: string;
  name: string;
  status: string;
};

export function DashboardPage() {
  const { state } = useAuth();
  const user = state.status === "authenticated" ? state.user : null;

  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    apiFetch<Assignment[]>("/domains/assigned")
      .then(setAssignments)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load assignments")
      );
  }, [user]);

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
      {user?.roles.includes("admin") && (
        <Typography variant="body2" sx={{ mb: 2 }}>
          Admin tools are available from the navigation bar.
        </Typography>
      )}
      {error && <Typography color="error">{error}</Typography>}
      {assignments === null && !error && <CircularProgress />}
      {assignments !== null && (
        <Card>
          <CardContent>
            <Typography variant="h6">My assignments</Typography>
            {assignments.length === 0 ? (
              <Typography>No domain assignments yet.</Typography>
            ) : (
              <List>
                {assignments.map((a) => (
                  <ListItem key={a.code}>
                    <ListItemText primary={`${a.name} (${a.code})`} secondary={`Status: ${a.status}`} />
                  </ListItem>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
