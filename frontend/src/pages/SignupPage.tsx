import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

const defaultVitals = {
  employee_range: "1-10",
  clients_per_year_range: "100-500",
  primary_software: "QuickBooks Online",
  deployment_type: "cloud",
  has_efin: true,
  it_support_provider: "Internal IT",
  remote_access: true,
  paper_files: false,
  sensitive_data_types: ["ssn", "tax_records"],
  coordinator_name: "",
  coordinator_title: "",
};

export function SignupPage() {
  const slug = window.location.host.split(".")[0];

  const [companyName, setCompanyName] = useState("Palmetto Tax");
  const [address, setAddress] = useState("123 Main St");
  const [workspaceEmail, setWorkspaceEmail] = useState(`admin@${slug}.app.wisp.llc`);
  const [funding, setFunding] = useState<"card" | "voucher">("voucher");
  const [voucherCode, setVoucherCode] = useState("WISP-2026-DEMO");
  const [vitals, setVitals] = useState(defaultVitals);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{
    kind: "voucher" | "card";
    checkoutId?: string;
    checkoutUrl?: string;
  } | null>(null);

  const updateVital = (field: string, value: unknown) => {
    setVitals((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch<{
        provisioned?: boolean;
        checkout_id?: string;
        checkout_url?: string;
      }>("/signup", {
        method: "POST",
        body: {
          company_name: companyName,
          address,
          workspace_email: workspaceEmail,
          funding,
          voucher_code: funding === "voucher" ? voucherCode : null,
          vitals,
        },
      });

      if (response.provisioned) {
        setSuccess({ kind: "voucher" });
      } else if (response.checkout_id) {
        setSuccess({
          kind: "card",
          checkoutId: response.checkout_id,
          checkoutUrl: response.checkout_url,
        });
      }
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Signup failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const confirmCardTest = async () => {
    if (!success?.checkoutId) return;
    setLoading(true);
    try {
      await apiFetch("/signup/test-confirm-card", {
        method: "POST",
        body: { event: "checkout.session.completed", checkout_id: success.checkoutId },
      });
      setSuccess({ kind: "voucher" });
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Confirmation failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (success?.kind === "voucher") {
    return (
      <Box sx={{ maxWidth: 600, mx: "auto", mt: 8, p: 2 }}>
        <Typography variant="h4" gutterBottom>
          Workspace ready
        </Typography>
        <Typography>
          Your workspace <strong>{slug}</strong> has been provisioned. An administrator invitation
          will be sent to {workspaceEmail}.
        </Typography>
      </Box>
    );
  }

  if (success?.kind === "card") {
    return (
      <Box sx={{ maxWidth: 600, mx: "auto", mt: 8, p: 2 }}>
        <Typography variant="h4" gutterBottom>
          Payment required
        </Typography>
        <Typography>
          Stripe Checkout session created. In production, you would now complete payment on Stripe.
        </Typography>
        {success.checkoutUrl && (
          <Button
            variant="contained"
            href={success.checkoutUrl}
            sx={{ mt: 2, mr: 2 }}
            data-testid="stripe-redirect"
          >
            Go to Stripe Checkout
          </Button>
        )}
        <Button
          variant="outlined"
          onClick={confirmCardTest}
          disabled={loading}
          sx={{ mt: 2 }}
          data-testid="test-confirm-card"
        >
          Simulate payment success (test)
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 600, mx: "auto", mt: 4, p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Create your workspace
      </Typography>
      <Typography variant="body1" sx={{ mb: 2 }}>
        Workspace: <strong>{slug}</strong>
      </Typography>
      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Company name"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Workspace email"
          value={workspaceEmail}
          onChange={(e) => setWorkspaceEmail(e.target.value)}
          fullWidth
          margin="normal"
          required
          type="email"
        />
        <FormControl component="fieldset" sx={{ mt: 2 }}>
          <FormLabel component="legend">Payment method</FormLabel>
          <RadioGroup
            row
            value={funding}
            onChange={(e) => setFunding(e.target.value as "card" | "voucher")}
          >
            <FormControlLabel value="card" control={<Radio />} label="Credit card" />
            <FormControlLabel value="voucher" control={<Radio />} label="Voucher" />
          </RadioGroup>
        </FormControl>
        {funding === "voucher" && (
          <TextField
            label="Voucher code"
            value={voucherCode}
            onChange={(e) => setVoucherCode(e.target.value)}
            fullWidth
            margin="normal"
            required
          />
        )}
        <Typography variant="h6" sx={{ mt: 3 }}>
          Corporate vitals
        </Typography>
        <TextField
          label="Employee range"
          value={vitals.employee_range}
          onChange={(e) => updateVital("employee_range", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Clients per year range"
          value={vitals.clients_per_year_range}
          onChange={(e) => updateVital("clients_per_year_range", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Primary software"
          value={vitals.primary_software}
          onChange={(e) => updateVital("primary_software", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Deployment type"
          value={vitals.deployment_type}
          onChange={(e) => updateVital("deployment_type", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="IT support provider"
          value={vitals.it_support_provider}
          onChange={(e) => updateVital("it_support_provider", e.target.value)}
          fullWidth
          margin="normal"
        />
        <TextField
          label="Coordinator name"
          value={vitals.coordinator_name}
          onChange={(e) => updateVital("coordinator_name", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        <TextField
          label="Coordinator title"
          value={vitals.coordinator_title}
          onChange={(e) => updateVital("coordinator_title", e.target.value)}
          fullWidth
          margin="normal"
          required
        />
        {error && (
          <Typography color="error" sx={{ mt: 2 }}>
            {error}
          </Typography>
        )}
        <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }} disabled={loading}>
          {loading ? <CircularProgress size={24} /> : "Create workspace"}
        </Button>
      </Box>
    </Box>
  );
}
