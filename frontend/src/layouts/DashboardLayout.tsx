import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function DashboardLayout() {
  const { state, logout } = useAuth();
  const navigate = useNavigate();

  const user = state.status === "authenticated" ? state.user : null;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            WISPGen
          </Typography>
          {user && (
            <>
              <Typography variant="body2" sx={{ mr: 2 }}>
                {user.email} ({user.roles.join(", ")})
              </Typography>
              <Button color="inherit" onClick={handleLogout}>
                Log out
              </Button>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box sx={{ mb: 2 }}>
          <Button component={Link} to="/dashboard" sx={{ mr: 1 }}>
            Dashboard
          </Button>
          {user?.roles.includes("admin") && (
            <>
              <Button component={Link} to="/admin/users" sx={{ mr: 1 }}>
                Users
              </Button>
              <Button component={Link} to="/admin/domains" sx={{ mr: 1 }}>
                Domains
              </Button>
              <Button component={Link} to="/admin/versions" sx={{ mr: 1 }}>
                Versions
              </Button>
            </>
          )}
          {user?.roles.includes("contributor") && (
            <Button component={Link} to="/domains" sx={{ mr: 1 }}>
              My domains
            </Button>
          )}
          {user?.roles.includes("reviewer") && (
            <Button component={Link} to="/review" sx={{ mr: 1 }}>
              Review
            </Button>
          )}
        </Box>
        <Outlet />
      </Container>
    </Box>
  );
}
