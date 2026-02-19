package main

import (
	"fmt"
	"net/http"
	"os/exec"
)

type JiraClient struct {
	url    string
	token  string
}

func (j *JiraClient) CreateIssue(title, description string) error {
	req, err := http.NewRequest("POST", j.url+"/rest/api/2/issue", nil)
	if err != nil {
		return fmt.Errorf("Failed to create issue: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", j.token))

	body := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s"
		}
	}`, title, description)

	req.Body = strings.NewReader(body)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("Failed to create issue: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Failed to create issue: %s", resp.Status)
	}

	fmt.Println("Issue created successfully")
	return nil
}

func main() {
	jira := &JiraClient{
		url:    "https://your-jira-instance.atlassian.net",
		token:  "your-jira-token",
	}

	err := jira.CreateIssue("Test Issue", "This is a test issue for the Go Agent with Jira integration.")
	if err != nil {
		fmt.Println(err)
		return
	}
}