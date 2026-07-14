Feature: Review workflow

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled user "admin@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "admin"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "reviewer"
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is signed in
    And a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"
    And "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in

  Scenario: REVW-01 Reviewer approves compiled answer
    When the reviewer approves domain "AC"
    Then the domain "AC" status is "approved"
    And the contributor receives a "domain_approved" notification

  Scenario: REVW-02 Edit produces AI revision and direct approval
    When the reviewer revises domain "AC" with prompt "Add more detail on access logs"
    Then the compiled answer narrative contains "access logs"
    And the domain "AC" status is "approved"
    And the contributor receives a "domain_revised_and_approved" notification

  Scenario: REVW-03 Reviewer defers decision
    When the reviewer defers domain "AC"
    Then the domain "AC" status is "in_progress"

  Scenario: REVW-04 Self-review shows warning
    Given domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "contributor@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is signed in
    When the reviewer approves domain "AC"
    Then the response includes a self-review warning

  Scenario: REVW-05 All approved completes the WISP
    Given all 14 domains are submitted for "contributor@palmetto.app.wisp.llc"
    When the reviewer approves the last domain
    Then the WISP version status is "complete"
    And the admin receives a "wisp_complete" notification
