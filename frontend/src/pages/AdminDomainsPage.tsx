import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_email?: string;
  reviewer_email?: string;
};

type User = {
  id: number;
  email: string;
  roles: string[];
  status: string;
};

export function AdminDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [picks, setPicks] = useState<Record<string, { contributor?: string; reviewer?: string }>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const loadDomains = () => {
    apiFetch<Domain[]>("/domains/unassigned")
      .then((rows) => {
        setDomains(rows);
        const init: Record<string, { contributor?: string; reviewer?: string }> = {};
        for (const d of rows) {
          init[d.code] = { contributor: d.contributor_email, reviewer: d.reviewer_email };
        }
        setPicks(init);
      })
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load domains"),
      );
  };

  const loadUsers = () => {
    apiFetch<User[]>("/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load users"),
      );
  };

  useEffect(() => {
    loadDomains();
    loadUsers();
  }, []);

  const assign = async (code: string) => {
    const { contributor, reviewer } = picks[code] ?? {};
    if (!contributor || !reviewer) {
      setError("Select both a contributor and a reviewer.");
      return;
    }
    setSaving((s) => ({ ...s, [code]: true }));
    setError(null);
    try {
      await apiFetch(`/domains/${code}/assign`, {
        method: "POST",
        body: { contributor_email: contributor, reviewer_email: reviewer },
      });
      loadDomains();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Assignment failed";
      setError(message);
    } finally {
      setSaving((s) => ({ ...s, [code]: false }));
    }
  };

  const candidates = (role: string) =>
    (users ?? []).filter((u) => u.status === "active" && u.roles.includes(role));

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Domains
      </Typography>
      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      {domains === null && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {domains !== null && (
        <Grid container spacing={2}>
          {domains.map((d) => (
            <Grid item xs={12} md={6} lg={4} key={d.code}>
              <Card variant="outlined" data-testid={`domain-card-${d.code}`} data-domain-code={d.code}>
                <CardContent>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                    <Typography variant="h6">
                      {d.name} ({d.code})
                    </Typography>
                    <Chip label={d.status.replace(/_/g, " ")} size="small" />
                  </Box>
                  <Box sx={{ display: "grid", gap: 2, mt: 2 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel id={`contributor-label-${d.code}`}>Contributor</InputLabel>
                      <Select
                        labelId={`contributor-label-${d.code}`}
                        value={picks[d.code]?.contributor ?? ""}
                        label="Contributor"
                        onChange={(e) =>
                          setPicks((p) => ({
                            ...p,
                            [d.code]: { ...p[d.code], contributor: e.target.value as string },
                          }))
                        }
                      >
                        {candidates("contributor").map((u) => (
                          <MenuItem key={u.id} value={u.email}>
                            {u.email}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl fullWidth size="small">
                      <InputLabel id={`reviewer-label-${d.code}`}>Reviewer</InputLabel>
                      <Select
                        labelId={`reviewer-label-${d.code}`}
                        value={picks[d.code]?.reviewer ?? ""}
                        label="Reviewer"
                        onChange={(e) =>
                          setPicks((p) => ({
                            ...p,
                            [d.code]: { ...p[d.code], reviewer: e.target.value as string },
                          }))
                        }
                      >
                        {candidates("reviewer").map((u) => (
                          <MenuItem key={u.id} value={u.email}>
                            {u.email}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </CardContent>
                <CardActions>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={saving[d.code] || !picks[d.code]?.contributor || !picks[d.code]?.reviewer}
                    onClick={() => assign(d.code)}
                  >
                    {saving[d.code] ? "Saving..." : "Assign"}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}
