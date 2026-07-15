import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

type User = {
  id: number;
  email: string;
  roles: string[];
  status: string;
};

type Invitation = {
  email: string;
  roles: string;
  token: string;
  expires_at: string;
  accepted_at: string | null;
};

const availableRoles = ["admin", "contributor", "reviewer"];

function formatRoles(roles: string): string {
  try {
    return (JSON.parse(roles) as string[]).join(", ");
  } catch {
    return roles;
  }
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [email, setEmail] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(["contributor"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);

  const loadUsers = () => {
    apiFetch<User[]>("/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load users")
      );
  };

  const loadInvitations = () => {
    apiFetch<Invitation[]>("/users/invitations")
      .then(setInvitations)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load invitations")
      );
  };

  useEffect(() => {
    loadUsers();
    loadInvitations();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiFetch("/users/invite", {
        method: "POST",
        body: { email, roles: selectedRoles.join(",") },
      });
      setEmail("");
      setSelectedRoles(["contributor"]);
      loadUsers();
      loadInvitations();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Invite failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const updateRoles = async (user: User, roles: string[]) => {
    try {
      await apiFetch(`/users/${user.id}/roles`, {
        method: "POST",
        body: { roles: roles.join(",") },
      });
      loadUsers();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Role update failed";
      setError(message);
    }
  };

  const toggleStatus = async (user: User) => {
    try {
      const endpoint = user.status === "active" ? "/deactivate" : "/reactivate";
      await apiFetch(`/users/${user.id}${endpoint}`, {
        method: "POST",
      });
      loadUsers();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Status change failed";
      setError(message);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await apiFetch(`/users/${deleteTarget.id}`, { method: "DELETE" });
      loadUsers();
      loadInvitations();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Delete failed";
      setError(message);
    } finally {
      setDeleteTarget(null);
    }
  };

  const statusColor = (status: string) => {
    if (status === "active") return "success";
    if (status === "deactivated") return "default";
    return "info";
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Users and invitations
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Invite user
          </Typography>
          <Box component="form" onSubmit={handleInvite}>
            <Grid container spacing={2} alignItems="flex-start">
              <Grid item xs={12} md={5}>
                <TextField
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  fullWidth
                  required
                />
              </Grid>
              <Grid item xs={12} md={5}>
                <FormControl fullWidth>
                  <InputLabel id="roles-label">Roles</InputLabel>
                  <Select
                    labelId="roles-label"
                    multiple
                    value={selectedRoles}
                    onChange={(e) => setSelectedRoles(e.target.value as string[])}
                    renderValue={(selected) => (selected as string[]).join(", ")}
                    label="Roles"
                  >
                    {availableRoles.map((role) => (
                      <MenuItem key={role} value={role}>
                        <Checkbox checked={selectedRoles.includes(role)} />
                        {role}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <Button type="submit" variant="contained" fullWidth disabled={loading}>
                  {loading ? <CircularProgress size={24} /> : "Invite"}
                </Button>
              </Grid>
            </Grid>
            {error && <Typography color="error" sx={{ mt: 2 }}>{error}</Typography>}
          </Box>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Users
          </Typography>
          {users === null && <CircularProgress />}
          {users && (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Email</TableCell>
                    <TableCell>Roles</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>
                        <FormControl fullWidth size="small">
                          <Select
                            multiple
                            value={u.roles}
                            onChange={(e) => updateRoles(u, e.target.value as string[])}
                            renderValue={(selected) => (selected as string[]).join(", ")}
                          >
                            {availableRoles.map((role) => (
                              <MenuItem key={role} value={role}>
                                <Checkbox checked={u.roles.includes(role)} />
                                {role}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </TableCell>
                      <TableCell>
                        <Chip label={u.status} color={statusColor(u.status) as never} size="small" />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => toggleStatus(u)}
                          sx={{ mr: 1 }}
                        >
                          {u.status === "active" ? "Deactivate" : "Reactivate"}
                        </Button>
                        <Button
                          variant="outlined"
                          color="error"
                          size="small"
                          onClick={() => setDeleteTarget(u)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Pending invitations
          </Typography>
          {invitations === null && <CircularProgress />}
          {invitations && invitations.length === 0 && (
            <Typography color="text.secondary">No pending invitations.</Typography>
          )}
          {invitations && invitations.length > 0 && (
            <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 2 }}>
              {invitations.map((inv) => (
                <Card key={inv.token} variant="outlined" data-testid={`invitation-${inv.email}`}>
                  <CardContent>
                    <Typography fontWeight="bold">{inv.email}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatRoles(inv.roles)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Expires: {new Date(inv.expires_at).toLocaleDateString()}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete user?</DialogTitle>
        <DialogContent>
          This will permanently remove {deleteTarget?.email} and any active invitations.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button onClick={confirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
