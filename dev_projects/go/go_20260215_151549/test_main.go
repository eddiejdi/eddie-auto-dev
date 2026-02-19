package main

import (
	"testing"
)

// TestTrackActivity tests the TrackActivity method of JiraIntegration
func TestTrackActivity(t *testing.T) {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}

	integration := JiraIntegration{jiraAPI, goAgentAPI}

	// Test case 1: Success with valid inputs
	err := integration.TrackActivity("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Test failed: %v", err)
	}
	t.Log("Success: TrackActivity with valid inputs")

	// Test case 2: Error with invalid input (zero value for title)
	err = integration.TrackActivity("", "Implement a new feature in the application")
	if err == nil {
		t.Errorf("Test failed: Expected error for empty title, but got none")
	}
	t.Log("Success: TrackActivity with empty title")

	// Test case 3: Error with invalid input (empty description)
	err = integration.TrackActivity("New Feature Request", "")
	if err == nil {
		t.Errorf("Test failed: Expected error for empty description, but got none")
	}
	t.Log("Success: TrackActivity with empty description")
}