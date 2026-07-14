import { Box, Button, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function TotpChallengePage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { verifyTotp } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await verifyTotp(code);
      navigate("/dashboard");
    } catch {
      setError("Invalid code. Please try again.");
    }
  };

  return (
    <Box sx={{ maxWidth: 400, mx: "auto", mt: 8, p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Two-factor authentication
      </Typography>
      <Typography sx={{ mb: 2 }}>
        Enter the 6-digit code from your authenticator app.
      </Typography>
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
