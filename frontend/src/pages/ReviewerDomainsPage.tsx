import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_id?: number;
  reviewer_id?: number;
};

export function ReviewerDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Review queue
      </Typography>
      {error && <Typography color="error">{error}</Typography>}
      {domains === null && <CircularProgress />}
      {domains !== null && domains.length === 0 && (
        <Typography>No domains awaiting review.</Typography>
      )}
      {domains !== null && (
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
          {domains.map((d) => (
            <Card key={d.code} data-domain-code={d.code}>
              <CardActionArea onClick={() => navigate(`/review/${d.code}`)}>
                <CardContent>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                    <Typography variant="h6">
                      {d.name} ({d.code})
                    </Typography>
                    <Chip label={d.status} size="small" />
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
}
