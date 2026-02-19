package main

import (
	"fmt"
	"log"

	"github.com/jira/go-jira/v2"
)

// JiraClient represents a client to interact with the Jira API.
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new instance of JiraClient.
func NewJiraClient(jiraURL, username, password string) (*JiraClient, error) {
	jiraOptions := jira.Options{
		Server: jiraURL,
		User:   username,
		Pass:  password,
	}

	client, err := jira.NewClientWithOptions(jiraOptions)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}

	return &JiraClient{client}, nil
}

// CreateIssue creates a new issue in the specified project.
func (jc *JiraClient) CreateIssue(projectKey string, summary, description string) (*jira.Issue, error) {
	project, err := jc.client.Projects.Get(projectKey)
	if err != nil {
		return nil, fmt.Errorf("failed to get project: %v", err)
	}

	issue := &jira.Issue{
	 Fields: jira.Fields{
			Title:       summary,
			Description: description,
			Priority:    jira.Priority{Id: "3"}, // 3 is the highest priority
			Status:     jira.Status{Id: "1"},   // 1 is the open status
		},
	}

	newIssue, err := jc.client.Issues.Create(project.Key, issue)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %v", err)
	}

	fmt.Printf("Created issue with ID: %s\n", newIssue.ID)
	return newIssue, nil
}

// main is the entry point of the program.
func main() {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	jc, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	projectKey := "YOUR_PROJECT_KEY"
	summary := "New feature request for Go Agent integration"
	description := "Implement Go Agent integration with Jira"

	newIssue, err := jc.CreateIssue(projectKey, summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
}