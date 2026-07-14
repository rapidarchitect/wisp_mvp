import {
  Box,
  Button,
  CircularProgress,
  TextField,
  Typography,
} from "@mui/material";
import { TOTP } from "otpauth";
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";

export function ActivatePage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const secret = useState(() => {
    const auth = new TOTP({ issuer: "WISPGen", label: "WISPGen" });
    return auth.secret.base32;
  })[0];

  const provisioningUri = new TOTP({
    secret,
    issuer: "WISPGen",
    label: "WISPGen",
  }).toString();

  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const totp = new TOTP({ secret });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiFetch("/users/accept", {
        method: "POST",
        body: { token, password, totp_secret: secret },
      });
      navigate("/login");
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Activation failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <Box sx={{ maxWidth: 400, mx: "auto", mt: 8, p: 2 }}>
        <Typography color="error">Invitation token is missing.</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 400, mx: "auto", mt: 8, p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Activate your account
      </Typography>
      <Typography sx={{ mb: 2 }}>
        Set a password and scan the QR code with your authenticator app.
      </Typography>
      <QRCodeSVG value={provisioningUri} style={{ marginBottom: 16 }} />
      <Typography variant="caption" component="div" sx={{ display: "block", mb: 2 }}>
        Test code: {totp.generate()}
      </Typography>
      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Authenticator code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          fullWidth
          margin="normal"
          slotProps={{ htmlInput: { maxLength: 6 } }}
          required
        />
        {error && (
          <Typography color="error" sx={{ mt: 2 }}>
            {error}
          </Typography>
        )}
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={loading}>
          {loading ? <CircularProgress size={24} /> : "Activate"}
        </Button>
      </Box>
    </Box>
  );
}
