package main

import (
	"testing"
)

// TestTrackActivityTestSuite é a estrutura para testar a função TrackActivity.
type TestTrackActivityTestSuite struct{}

func (s *TestTrackActivityTestSuite) TestTrackActivity_Success(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	TrackActivity(jira, goAgent)

	expectedOutput := "Creating issue: New Feature Request - Request to implement a new feature in the application.\nSending event: featureRequest - map[string]interface {}{eventType:featureRequest,title:New Feature Request,description:Request to implement a new feature in the application.}\nActivity tracked successfully."
	t.Log(expectedOutput)
}

func (s *TestTrackActivityTestSuite) TestTrackActivity_Error(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	// Simulando um erro ao criar o issue
	err := jira.CreateIssue("", "")
	if err != nil {
		t.Log("Error creating issue:", err)
	}

	expectedOutput := "Failed to create issue: error"
	t.Log(expectedOutput)
}