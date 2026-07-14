import {
  Box,
  Button,
  Container,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { Link } from "react-router-dom";

export function LandingPage() {
  const [workspace, setWorkspace] = useState("");

  const goToWorkspace = (path: string) => {
    const slug = workspace.trim().toLowerCase();
    if (!slug) return;
    const host = `${slug}.localhost:5173`;
    window.location.href = `http://${host}${path}`;
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Typography variant="h3" gutterBottom>
        WISPGen
      </Typography>
      <Typography variant="body1" sx={{ mb: 4 }}>
        Build your Written Information Security Program.
      </Typography>
      <Box sx={{ display: "flex", gap: 2, mb: 4 }}>
        <TextField
          label="Workspace address"
          placeholder="yourfirm"
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value)}
          fullWidth
          helperText="Enter your workspace slug to continue"
        />
      </Box>
      <Box sx={{ display: "flex", gap: 2 }}>
        <Button
          variant="contained"
          onClick={() => goToWorkspace("/signup")}
          disabled={!workspace.trim()}
        >
          Sign up
        </Button>
        <Button
          variant="outlined"
          component={Link}
          to="/login"
          onClick={(e) => {
            e.preventDefault();
            goToWorkspace("/login");
          }}
          disabled={!workspace.trim()}
        >
          Log in
        </Button>
      </Box>
    </Container>
  );
}
