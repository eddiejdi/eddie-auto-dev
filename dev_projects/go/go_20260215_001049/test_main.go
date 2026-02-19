package main

import (
	"testing"
)

// TestTrackActivity tests the TrackActivity method of JiraIntegration
func TestTrackActivity(t *testing.T) {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}

	integration := JiraIntegration{jiraAPI, goAgentAPI}

	testCases := []struct {
		eventType string
		eventData map[string]string
		expectedError error
	}{
		{"User Activity", map[string]string{"user": "john_doe", "action": "login"}, nil},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("Event: %s, Data: %+v", tc.eventType, tc.eventData), func(t *testing.T) {
			err := integration.TrackActivity(tc.eventType, tc.eventData)
			if err != nil && err.Error() != tc.expectedError.Error() {
				t.Errorf("Expected error: %v, got: %v", tc.expectedError, err)
			} else if err == nil && tc.expectedError != nil {
				t.Errorf("Expected error: %v, got no error", tc.expectedError)
			}
		})
	}
}