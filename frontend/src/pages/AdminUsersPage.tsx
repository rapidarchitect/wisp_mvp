import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  FormControl,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Select,
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

const availableRoles = ["admin", "contributor", "reviewer"];

export function AdminUsersPage() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [email, setEmail] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(["contributor"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadUsers = () => {
    apiFetch<User[]>("/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load users")
      );
  };

  useEffect(() => {
    loadUsers();
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
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Invite failed";
      setError(message);
    } finally {
      setLoading(false);
    }
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
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              fullWidth
              margin="normal"
              required
            />
            <FormControl fullWidth margin="normal">
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
            {error && <Typography color="error" sx={{ mt: 2 }}>{error}</Typography>}
            <Button type="submit" variant="contained" sx={{ mt: 2 }} disabled={loading}>
              {loading ? <CircularProgress size={24} /> : "Send invitation"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Users
          </Typography>
          {users === null && <CircularProgress />}
          {users && (
            <List>
              {users.map((u) => (
                <ListItem key={u.id}>
                  <ListItemText
                    primary={u.email}
                    secondary={`${u.roles.join(", ")} — ${u.status}`}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
