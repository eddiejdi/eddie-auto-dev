package main

import (
	"testing"
)

// TestIntegratorScheduleJiraIssue tests the ScheduleJiraIssue method of the Integrator struct
func TestIntegratorScheduleJiraIssue(t *testing.T) {
	jiraClient := &MockJiraAPI{}
	goAgentClient := &GoAgentAPI{}

	integrator := NewIntegrator(jiraClient, goAgentClient)

	// Test case 1: Success with valid data
	err := integrator.ScheduleJiraIssue("New Feature", "Implement new feature in the application")
	if err != nil {
		t.Errorf("Test failed: ScheduleJiraIssue should not return an error for valid input")
	}
}

// TestIntegratorScheduleJiraIssue tests the ScheduleJiraIssue method of the Integrator struct
func TestIntegratorScheduleJiraIssueError(t *testing.T) {
	jiraClient := &MockJiraAPI{}
	goAgentClient := &GoAgentAPI{}

	integrator := NewIntegrator(jiraClient, goAgentClient)

	// Test case 2: Error with invalid data (empty summary)
	err := integrator.ScheduleJiraIssue("", "Implement new feature in the application")
	if err == nil {
		t.Errorf("Test failed: ScheduleJiraIssue should return an error for empty input")
	}
}

// MockJiraAPI is a mock implementation of JiraClient
type MockJiraAPI struct{}

func (m *MockJiraAPI) CreateIssue(summary string, description string) error {
	return nil // Simulate successful creation
}