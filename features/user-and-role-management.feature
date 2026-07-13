Feature: User and Role Management

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled admin "admin@palmetto.app.wisp.llc" with password "AdminPass123!"

  Scenario: Invite user with two roles (USER-01)
    Given "admin@palmetto.app.wisp.llc" is signed in
    When the admin invites "jane@palmetto.app.wisp.llc" with roles "contributor,reviewer"
    Then an invitation exists for "jane@palmetto.app.wisp.llc" with roles "contributor,reviewer"
    And the invitation expires in 7 days

  Scenario: Invited user activates account (USER-02)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And the admin invites "sam@palmetto.app.wisp.llc" with roles "contributor"
    When the invited user accepts with password "SecurePass123!" and TOTP secret "JBSWY3DPEHPK3PXP"
    Then a user exists for "sam@palmetto.app.wisp.llc" with roles "contributor"
    And the user can log in with password "SecurePass123!" and TOTP "JBSWY3DPEHPK3PXP"

  Scenario: One user holds all three roles (USER-03)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And an enrolled user "multi@palmetto.app.wisp.llc" with password "TempPass123!"
    When the admin sets roles for "multi@palmetto.app.wisp.llc" to "admin,contributor,reviewer"
    Then the user "multi@palmetto.app.wisp.llc" has roles "admin,contributor,reviewer"

  Scenario: Duplicate invitation rejected (USER-04)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And the admin invites "jane@palmetto.app.wisp.llc" with roles "contributor"
    When the admin invites "jane@palmetto.app.wisp.llc" with roles "reviewer"
    Then the invitation is rejected with "duplicate_invitation"

  Scenario: Expired invitation link refused (USER-05)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And the admin invites "expired@palmetto.app.wisp.llc" with roles "contributor"
    When 7 days pass
    And the invited user accepts with password "SecurePass123!" and TOTP secret "JBSWY3DPEHPK3PXP"
    Then the acceptance is rejected with "invitation_expired"

  Scenario: Deactivation flags domains, keeps answers (USER-06)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And an enrolled user "deactivate@palmetto.app.wisp.llc" with password "TempPass123!" and roles "contributor,reviewer"
    And domain "AC" is assigned to "deactivate@palmetto.app.wisp.llc" as contributor and "admin@palmetto.app.wisp.llc" as reviewer
    And "deactivate@palmetto.app.wisp.llc" has answered a question in domain "AC"
    When the admin deactivates "deactivate@palmetto.app.wisp.llc"
    Then the user "deactivate@palmetto.app.wisp.llc" is deactivated
    And domain "AC" is flagged as unassigned
    And the answer in domain "AC" is preserved
