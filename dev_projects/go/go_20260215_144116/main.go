package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/go-jira/jira/v4"
)

type JiraClient struct {
	client *jira.Client
}

func NewJiraClient(url, token string) (*JiraClient, error) {
	config := &jira.Config{
		Server:  url,
		User:   "your_username",
		Token:  token,
	}

	jiraClient, err := jira.New(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}

	return &JiraClient{jiraClient}, nil
}

func (jc *JiraClient) CreateIssue(title, description string) (*jira.Issue, error) {
	projectKey := "YOUR_PROJECT_KEY"
	labels := []string{"bug"}

	params := jira.NewCreateIssueParams()
	params.SetTitle(title)
	params.SetDescription(description)
	params.SetProject(projectKey)
	params.SetLabels(labels)

	issue, err := jc.client.CreateIssue(params)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %v", err)
	}

	fmt.Printf("Created issue: %+v\n", issue)
	return issue, nil
}

func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	title := "Bug in Go Agent integration"
	description := "Go Agent is not working as expected with Jira."

	issue, err := jiraClient.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
}