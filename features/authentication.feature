Feature: Authentication

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled user "admin@palmetto.app.wisp.llc" with password "CorrectHorseBatteryStaple"

  Scenario: First login requires TOTP enrollment (AUTH-01)
    When the user logs in with password "CorrectHorseBatteryStaple"
    Then the response requires TOTP enrollment
    And the user has a TOTP secret

  Scenario: Login with password and TOTP (AUTH-02)
    Given the user has enrolled TOTP
    When the user logs in with password "CorrectHorseBatteryStaple" and current TOTP
    Then a session is created

  Scenario: Wrong password rejected (AUTH-03)
    When the user logs in with password "wrongpassword"
    Then the login is rejected with "invalid_credentials"
    And no session is created

  Scenario: Wrong TOTP counts toward lockout (AUTH-04)
    Given the user has enrolled TOTP
    When the user logs in with password "CorrectHorseBatteryStaple" and TOTP "000000"
    Then the login is rejected with "invalid_credentials"
    And a failed login attempt is recorded

  Scenario: Lock after 5 failed attempts (AUTH-05)
    When the user logs in with password "wrongpassword" 5 times
    Then the account is locked for 15 minutes
    When the user logs in with password "wrongpassword" again
    Then the login is rejected with "account_locked"
    And no session is created

  Scenario: Expired session preserves saved work (AUTH-06)
    Given the user has a session issued 8 hours ago
    And the user saved an answer "yes"
    When the user uses the session after 8 hours and 1 minute
    Then the session is rejected as expired
    And the answer "yes" still exists
