Feature: WISP versioning and export

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled admin "admin@palmetto.app.wisp.llc" with password "AdminPass123!" and roles "admin"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "reviewer"
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is signed in
    And a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"

  Scenario: VERS-01 Draft export carries DRAFT watermark
    Given "admin@palmetto.app.wisp.llc" is signed in
    And the WISP version status is "in_progress"
    When the admin exports the current version
    Then the export response is a PDF
    And the PDF contains "DRAFT"

  Scenario: VERS-02 Complete WISP exports clean
    Given "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in
    And the reviewer approves domain "AC"
    And the WISP version status is "complete"
    And "admin@palmetto.app.wisp.llc" is signed in
    When the admin exports the current version
    Then the export response is a PDF
    And the PDF does not contain "DRAFT"

  Scenario: VERS-03 New version clones approved baseline
    Given "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in
    And the reviewer approves domain "AC"
    And the WISP version status is "complete"
    And "admin@palmetto.app.wisp.llc" is signed in
    When the admin starts a new version
    Then a second WISP version exists
    And the new version status is "in_progress"
    And domain "AC" in the new version has a compiled answer

  Scenario: VERS-04 Only one version in progress
    Given "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in
    And the reviewer approves domain "AC"
    And the WISP version status is "complete"
    And "admin@palmetto.app.wisp.llc" is signed in
    And the admin starts a new version
    When the admin starts a second version
    Then the request is rejected with "version_in_progress"

  Scenario: VERS-05 Prior versions remain exportable
    Given "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in
    And the reviewer approves domain "AC"
    And the WISP version status is "complete"
    And "admin@palmetto.app.wisp.llc" is signed in
    And the admin starts a new version
    When the admin exports version 1
    Then the export response is a PDF
