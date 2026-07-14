import { Box, Button, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function EnrollTotpPage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { completeEnrollment } = useAuth();
  const navigate = useNavigate();

  const uri = localStorage.getItem("wispgen_pending_uri") || "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await completeEnrollment(code);
      localStorage.removeItem("wispgen_pending_uri");
      navigate("/dashboard");
    } catch {
      setError("Invalid code. Please try again.");
    }
  };

  return (
    <Box sx={{ maxWidth: 400, mx: "auto", mt: 8, p: 2, textAlign: "center" }}>
      <Typography variant="h4" gutterBottom>
        Set up two-factor authentication
      </Typography>
      <Typography sx={{ mb: 2 }}>
        Scan this QR code with your authenticator app, then enter the 6-digit code.
      </Typography>
      {uri && <QRCodeSVG value={uri} style={{ marginBottom: 16 }} />}
      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Authenticator code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          fullWidth
          slotProps={{ htmlInput: { maxLength: 6 } }}
          required
        />
        {error && (
          <Typography color="error" sx={{ mt: 2 }}>
            {error}
          </Typography>
        )}
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>
          Verify
        </Button>
      </Box>
    </Box>
  );
}
