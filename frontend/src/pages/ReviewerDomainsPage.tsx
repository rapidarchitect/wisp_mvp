import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_id?: number;
  reviewer_id?: number;
};

const filters = ["all", "in_review", "approved"];

const statusColor: Record<string, "default" | "primary" | "warning" | "success" | "info"> = {
  in_review: "warning",
  approved: "success",
};

export function ReviewerDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const navigate = useNavigate();

  useEffect(() => {
    apiFetch<Domain[]>("/domains/assigned")
      .then((rows) =>
        setDomains(rows.filter((d) => d.status === "in_review" || d.status === "approved")),
      )
      .catch((err) =>
        setError(
          err instanceof ApiResponseError ? err.error.message : "Failed to load assignments",
        ),
      );
  }, []);

  const filtered = useMemo(() => {
    if (domains === null) return null;
    if (filter === "all") return domains;
    return domains.filter((d) => d.status === filter);
  }, [domains, filter]);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Review queue
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
        <>
          <Tabs value={filter} onChange={(_, v) => setFilter(v)} sx={{ mb: 2 }}>
            {filters.map((f) => (
              <Tab
                key={f}
                value={f}
                label={f.replace(/_/g, " ")}
                data-testid={`review-filter-${f}`}
              />
            ))}
          </Tabs>
          {filtered!.length === 0 && (
            <Typography>No domains in this queue.</Typography>
          )}
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
            {filtered!.map((d) => (
              <Card key={d.code} data-domain-code={d.code} data-testid={`review-card-${d.code}`}>
                <CardActionArea onClick={() => navigate(`/review/${d.code}`)}>
                  <CardContent>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography variant="h6">
                        {d.name} ({d.code})
                      </Typography>
                      <Chip label={d.status.replace(/_/g, " ")} color={statusColor[d.status] ?? "default"} size="small" />
                    </Box>
                    <Button size="small" variant="outlined" sx={{ mt: 1 }}>
                      Review
                    </Button>
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Box>
        </>
      )}
    </Box>
  );
}
