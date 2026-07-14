import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

type Version = {
  id: number;
  number: number;
  status: string;
  created_at: string;
  completed_at: string | null;
};

export function AdminVersionsPage() {
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadVersions = () => {
    apiFetch<Version[]>("/versions")
      .then(setVersions)
      .catch((err) =>
        setError(
          err instanceof ApiResponseError ? err.error.message : "Failed to load versions",
        ),
      );
  };

  useEffect(() => {
    loadVersions();
  }, []);

  const exportVersion = async (versionNumber?: number) => {
    setLoading(true);
    setMessage(null);
    try {
      const path = versionNumber
        ? `/versions/${versionNumber}/export`
        : "/versions/current/export";
      const response = await fetch(`/api/v1${path}`, {
        method: "GET",
        credentials: "include",
        headers: { Authorization: `Bearer ${localStorage.getItem("wispgen_token")}` },
      });
      if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = response.headers.get("Content-Disposition") || "";
      const filenameMatch = disposition.match(/filename="([^"]+)"/);
      a.download = filenameMatch ? filenameMatch[1] : `wisp-export.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setMessage(`Exported ${a.download}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setLoading(false);
    }
  };

  const startNewVersion = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await apiFetch("/versions", { method: "POST" });
      setMessage("New version started.");
      loadVersions();
    } catch (err) {
      setError(
        err instanceof ApiResponseError ? err.error.message : "Failed to start version",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Versions and export
      </Typography>

      {error && <Typography color="error">{error}</Typography>}
      {message && <Typography color="success">{message}</Typography>}

      <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          onClick={() => exportVersion()}
          disabled={loading}
        >
          Export current version
        </Button>
        <Button
          variant="outlined"
          onClick={startNewVersion}
          disabled={loading}
        >
          Start new version
        </Button>
      </Box>

      {versions === null && <CircularProgress />}
      {versions !== null && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Version history
            </Typography>
            {versions.length === 0 ? (
              <Typography>No versions found.</Typography>
            ) : (
              <List>
                {versions.map((v) => (
                  <ListItem key={v.id} sx={{ display: "flex", gap: 2 }}>
                    <ListItemText
                      primary={`Version ${v.number}`}
                      secondary={`Created ${v.created_at}`}
                    />
                    <Chip label={v.status} />
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => exportVersion(v.number)}
                      disabled={loading}
                    >
                      Export
                    </Button>
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
