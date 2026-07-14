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

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_email?: string;
  reviewer_email?: string;
};

export function AdminDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Domain[]>("/domains/unassigned")
      .then(setDomains)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load domains")
      );
  }, []);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Domains
      </Typography>
      {error && <Typography color="error">{error}</Typography>}
      {domains === null && !error && <CircularProgress />}
      {domains !== null && (
        <Card>
          <CardContent>
            <Typography variant="h6">Unassigned domains</Typography>
            {domains.length === 0 ? (
              <Typography>All domains are assigned.</Typography>
            ) : (
              <List>
                {domains.map((d) => (
                  <ListItem key={d.code}>
                    <ListItemText
                      primary={`${d.name} (${d.code})`}
                      secondary={`Status: ${d.status}`}
                    />
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
