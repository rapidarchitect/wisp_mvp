import { Box, Button, CircularProgress, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const slug = window.location.host.split(".")[0];
  const [email, setEmail] = useState(`admin@${slug}.app.wisp.llc`);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const step = await login(email, password);
      if (step.kind === "session") {
        navigate("/dashboard");
      } else if (step.kind === "enrollment_required") {
        navigate("/enroll-totp");
      } else {
        navigate("/totp");
      }
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 400, mx: "auto", mt: 8, p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Log in to {slug}
      </Typography>
      <Box component="form" onSubmit={handleSubmit} autoComplete="off">
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          fullWidth
          margin="normal"
          required
          autoComplete="off"
          inputProps={{ "data-testid": "login-email" }}
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          margin="normal"
          required
          autoComplete="new-password"
          inputProps={{ "data-testid": "login-password" }}
        />
        {error && (
          <Typography color="error" sx={{ mt: 2 }}>
            {error}
          </Typography>
        )}
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={loading}>
          {loading ? <CircularProgress size={24} /> : "Continue"}
        </Button>
      </Box>
    </Box>
  );
}
