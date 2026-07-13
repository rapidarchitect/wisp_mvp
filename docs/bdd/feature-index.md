# WISPGen Feature Index

This inventory maps each Gherkin feature file to its scenarios and owning SPEC task. Feature files are spec and require human approval before creation or modification.

| Feature file | Scenario ID | Scenario title | Steps module | SPEC Task | Status |
|---|---|---|---|---|---|
| signup-and-onboarding | SIGN-01 | Card signup provisions workspace | test_signup_and_onboarding | Task 06 | planned |
| signup-and-onboarding | SIGN-02 | Voucher skips card payment | test_signup_and_onboarding | Task 06 | planned |
| signup-and-onboarding | SIGN-03 | Declined card leaves no workspace | test_signup_and_onboarding | Task 06 | planned |
| signup-and-onboarding | SIGN-04 | Workspace address must be unique | test_signup_and_onboarding | Task 06 | planned |
| signup-and-onboarding | SIGN-05 | Corporate vitals validation (outline) | test_signup_and_onboarding | Task 06 | planned |
| authentication | AUTH-01 | First login requires TOTP enrollment | test_authentication | Task 04 | planned |
| authentication | AUTH-02 | Login with password and TOTP | test_authentication | Task 04 | planned |
| authentication | AUTH-03 | Wrong password rejected | test_authentication | Task 03 | planned |
| authentication | AUTH-04 | Wrong TOTP counts toward lockout | test_authentication | Task 04 | planned |
| authentication | AUTH-05 | Lock after 5 failed attempts | test_authentication | Task 03 | planned |
| authentication | AUTH-06 | Expired session preserves saved work | test_authentication | Task 03 | planned |
| authentication | AUTH-07 | Password reset via 30-min link | test_authentication | Task 05 | planned |
| user-and-role-management | USER-01 | Invite user with two roles | test_user_and_role_management | Task 07 | planned |
| user-and-role-management | USER-02 | Invited user activates account | test_user_and_role_management | Task 07 | planned |
| user-and-role-management | USER-03 | One user holds all three roles | test_user_and_role_management | Task 07 | planned |
| user-and-role-management | USER-04 | Duplicate invitation rejected | test_user_and_role_management | Task 07 | planned |
| user-and-role-management | USER-05 | Expired invitation link refused | test_user_and_role_management | Task 07 | planned |
| user-and-role-management | USER-06 | Deactivation flags domains, keeps answers | test_user_and_role_management | Task 07 | planned |
| domain-seeding-and-questions | SEED-01 | 14 domains seeded, 5-10 questions each | test_domain_seeding_and_questions | Task 09 | planned |
| domain-seeding-and-questions | SEED-02 | Demo company after deployment | test_domain_seeding_and_questions | Task 09 | planned |
| domain-seeding-and-questions | SEED-03 | Research outage degrades gracefully | test_domain_seeding_and_questions | Task 09 | planned |
| domain-seeding-and-questions | SEED-04 | Admin adds custom question | test_domain_seeding_and_questions | Task 10 | planned |
| domain-seeding-and-questions | SEED-05 | Admin disables seeded question | test_domain_seeding_and_questions | Task 10 | planned |
| domain-seeding-and-questions | SEED-06 | Regeneration only when unanswered | test_domain_seeding_and_questions | Task 10 | planned |
| domain-assignment | ASSN-01 | Assign contributor and reviewer | test_domain_assignment | Task 12 | green |
| domain-assignment | ASSN-02 | One contributor, one reviewer at a time | test_domain_assignment | Task 12 | green |
| domain-assignment | ASSN-03 | Reassignment preserves work | test_domain_assignment | Task 12 | green |
| domain-assignment | ASSN-04 | Contributors see only assigned domains | test_domain_assignment | Task 12 | green |
| domain-assignment | ASSN-05 | Unassigned domains flagged to Admin | test_domain_assignment | Task 12 | green |
| contributor-questionnaire | QSTN-01 | Answer triggers up to 3 AI follow-ups | test_contributor_questionnaire | Task 13 | planned |
| contributor-questionnaire | QSTN-02 | AI compiles domain final answer | test_contributor_questionnaire | Task 14 | planned |
| contributor-questionnaire | QSTN-03 | Submission sends domain to review | test_contributor_questionnaire | Task 14 | planned |
| contributor-questionnaire | QSTN-04 | Skips defer but block submission | test_contributor_questionnaire | Task 13 | planned |
| contributor-questionnaire | QSTN-05 | Save and resume exact progress | test_contributor_questionnaire | Task 13 | planned |
| contributor-questionnaire | QSTN-06 | AI outage falls back to plain answer | test_contributor_questionnaire | Task 13 | planned |
| review-workflow | REVW-01 | Reviewer approves compiled answer | test_review_workflow | Task 15 | planned |
| review-workflow | REVW-02 | Edit produces AI revision, direct approval | test_review_workflow | Task 15 | planned |
| review-workflow | REVW-03 | Reviewer defers decision | test_review_workflow | Task 15 | planned |
| review-workflow | REVW-04 | Self-review allowed with warning | test_review_workflow | Task 15 | planned |
| review-workflow | REVW-05 | All approved completes the WISP | test_review_workflow | Task 15 | planned |
| wisp-versioning-and-export | VERS-01 | Draft export carries watermark | test_wisp_versioning_and_export | Task 16 | planned |
| wisp-versioning-and-export | VERS-02 | Complete WISP exports clean | test_wisp_versioning_and_export | Task 16 | planned |
| wisp-versioning-and-export | VERS-03 | New version clones approved baseline | test_wisp_versioning_and_export | Task 16 | planned |
| wisp-versioning-and-export | VERS-04 | Only one version in progress | test_wisp_versioning_and_export | Task 16 | planned |
| wisp-versioning-and-export | VERS-05 | Prior versions remain exportable | test_wisp_versioning_and_export | Task 16 | planned |

Scenario-exempt tasks: Task 01, Task 02, Task 08, Task 11, Task 19.
