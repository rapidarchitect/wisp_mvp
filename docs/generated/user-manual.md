# WISPGen User Manual

WISPGen helps small accounting and tax firms build a Written Information Security Program (WISP) that satisfies IRS Publication 4557 and FTC Safeguards Rule expectations. This manual covers the everyday workflows for firm administrators, contributors, and reviewers.

---

## 1. Creating an account

A firm starts by signing up at the WISPGen landing page.

1. Choose a workspace address, for example `demo.app.wisp.llc`. This address must be unique.
2. Enter company vitals such as employee range, primary software, and the coordinator who will own the WISP.
3. Choose payment: enter a card for Stripe Checkout, or apply a voucher code.
4. Submit the form. WISPGen provisions the workspace, creates the first admin account, and seeds 14 security domains.

After provisioning, you will see the TOTP enrollment screen. Scan the QR code with an authenticator app, enter the generated code, and save the recovery codes.

![Signup page](screenshots/signup-page.png)

---

## 2. Logging in

Return to your workspace address and log in in two steps.

1. Enter your email and password.
2. Click **Continue**.
3. Open your authenticator app and enter the six-digit code.
4. Click **Verify**.

If your TOTP is wrong five times in a row, the account locks for 15 minutes. Use the password-reset link if you forget your password; the link expires in 30 minutes.

![Login page](screenshots/login-page.png)

---

## 3. Dashboard overview

The dashboard shows the overall state of your WISP as a card grid.

- Each card represents one of the 14 security domains and shows its current status.
- A role-aware button at the top gives fast access to the right page: **Go to review queue** for reviewers, **My domains** for contributors, or **Manage domains** for admins who are not also contributors/reviewers.
- The sidebar gives admins access to Users, Domains, and Versions.
- Contributors see **My domains**; reviewers see **Review**.

Click any card or sidebar link to move to the next step.

![Dashboard](screenshots/dashboard.png)

---

## 4. Inviting and managing users

Only admins can invite users. A single user can hold one, two, or all three roles: admin, contributor, and reviewer.

1. Open **Users** from the sidebar.
2. Enter the new user's email.
3. Select one or more roles from the dropdown.
4. Click **Invite**.

The invitation appears as a card in the **Pending invitations** section. WISPGen emails the user an activation link that is valid for 7 days. The invitee sets a password and enrolls TOTP on first login.

The Users page also lists all existing users. Admins can change a user's roles from the table, deactivate or reactivate an account, or delete a user permanently after confirming the action.

![Users and invitations](screenshots/users-page.png)

---

## 5. Assigning contributors and reviewers to domains

Each of the 14 security domains needs exactly one contributor and one reviewer at a time. Admins assign people from the **Domains** page, which lists every unassigned domain as a card.

1. Open **Domains** from the sidebar.
2. Find an unassigned domain, for example **Audit (AU)**.
3. Choose a contributor from the **Contributor** dropdown.
4. Choose a reviewer from the **Reviewer** dropdown.
5. Click **Assign**.

The card disappears from the unassigned list, the domain moves to `assigned`, and it appears in the contributor's **My domains** list and the reviewer's **Review** queue.

![Domain assignment](screenshots/domains-page.png)

---

## 6. Answering the questionnaire

Contributors answer one yes-or-no question at a time for each assigned domain.

1. Click **My domains** in the sidebar.
2. Select a domain, for example **Access Control (AC)**.
3. Use the progress bar and stepper to track your position.
4. Answer the current question with **Yes** or **No**. If the answer is **Yes**, WISPGen may generate up to three follow-up questions about how the control is implemented.
5. Fill in each follow-up response and move to the next question with the **Next** button.
6. When every enabled question and follow-up is complete, the summary panel appears on the last step. Click **Compile** to generate the domain narrative, then **Submit** to send it to the reviewer.

Use **Previous** and **Next** to review earlier answers. Your answers are saved immediately, so you can leave and resume later.

If an AI service is unavailable, WISPGen waives the follow-up questions and records the plain answer so work can continue.

![Questionnaire](screenshots/questionnaire-page.png)

---

## 7. Reviewing and approving domains

The **Review** page is a filterable card queue. Use the **all**, **in review**, and **approved** tabs to focus on the domains you need.

1. Click **Review** in the sidebar.
2. Select a domain card from the queue.
3. Read the compiled narrative and the answers.
4. Choose one of the following actions:
   - **Approve** to mark the domain complete.
   - **Defer** to return it to the contributor for more information.
   - Enter a revision prompt and click **Revise and approve** to ask the AI to rewrite the narrative before approval.

When a reviewer is also the contributor for a domain, WISPGen shows a self-review warning. Self-review is allowed but flagged.

![Review queue](screenshots/review-page.png)

---

## 8. Exporting the WISP PDF

Once every domain in the current WISP version is approved, the version is complete. Admins export the final PDF from the **Versions** page.

1. Open **Versions** from the sidebar.
2. The completed version appears without a **DRAFT** watermark.
3. Click **Export PDF** to download the clean WISP.

Draft exports, available while any domain is still pending, include a **DRAFT** watermark.

![Versions and export](screenshots/versions-page.png)

---

## 9. Version lifecycle

WISPGen keeps a history of WISP versions.

- When the current version is complete, you can start a new version. The new version clones the approved baseline and resets only the domains you choose to update.
- Only one version can be **in_progress** at a time.
- Older completed versions remain exportable for compliance records.

To start a new version, use the **Create new version** button on the Versions page after the current version is complete.

---

## 10. Getting help

For deployment and infrastructure questions, see `infra/README.md` in the project repository. For application issues, contact the workspace administrator or the person who provisioned your WISPGen instance.
