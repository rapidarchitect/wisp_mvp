Feature: Signup and Onboarding

  Background:
    Given the visitor uses the "palmetto" workspace address

  Scenario: Card signup provisions workspace (SIGN-01)
    Given the visitor provides valid corporate vitals
    And the visitor chooses "card" payment
    When the visitor submits signup
    Then a Stripe Checkout session is created
    When the payment is confirmed
    Then a tenant workspace is provisioned
    And an initial WISP version exists
    And 14 domains exist

  Scenario: Voucher skips card payment (SIGN-02)
    Given a valid voucher "WISP-2026-DEMO"
    And the visitor provides valid corporate vitals
    And the visitor chooses "voucher" payment with code "WISP-2026-DEMO"
    When the visitor submits signup
    Then no Stripe Checkout session is created
    And a tenant workspace is provisioned
    And the voucher is marked as redeemed

  Scenario: Declined card leaves no workspace (SIGN-03)
    Given the visitor provides valid corporate vitals
    And the visitor chooses "card" payment
    When the visitor submits signup
    And Stripe declines the card
    Then no tenant workspace is provisioned
    And no tenant DB file is created

  Scenario: Workspace address must be unique (SIGN-04)
    Given a tenant already exists with slug "palmetto"
    And the visitor provides valid corporate vitals
    And the visitor chooses "voucher" payment with code "WISP-2026-UNIQUE"
    When the visitor submits signup
    Then the signup is rejected with "slug_taken"

  Scenario Outline: Corporate vitals validation (SIGN-05)
    Given the visitor provides corporate vitals with <field> "<value>"
    And the visitor chooses "voucher" payment with code "WISP-2026-<example>"
    When the visitor submits signup
    Then the signup is rejected with "<error>"

    Examples:
      | field            | value | error          | example |
      | coordinator_name |       | vitals_invalid | 001     |
      | employee_range   |       | vitals_invalid | 002     |
      | primary_software |       | vitals_invalid | 003     |
