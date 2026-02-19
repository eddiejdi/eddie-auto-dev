package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API.
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraClientImpl implementa o JiraClient interface usando HTTP requests.
type JiraClientImpl struct{}

func (j *JiraClientImpl) CreateIssue(title, description string) error {
	url := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	reqBody := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s",
			"project": {
				"id": "YOUR_PROJECT_ID"
			},
			"issuetype": {
				"name": "Bug"
			}
		}
	}`, title, description)

	req, err := http.NewRequest("POST", url, strings.NewReader(reqBody))
	if err != nil {
		return err
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Failed to create issue: %s", resp.Status)
	}

	return nil
}

// GoAgentClientImpl implementa o GoAgentClient interface usando HTTP requests.
type GoAgentClientImpl struct{}

func (g *GoAgentClientImpl) SendStatus(status string) error {
	url := "https://your-go-agent-instance.com/api/v1/status"
	reqBody := fmt.Sprintf(`{
		"status": "%s",
		"message": "Your job is done!"
	}`, status)

	req, err := http.NewRequest("POST", url, strings.NewReader(reqBody))
	if err != nil {
		return err
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Failed to send status: %s", resp.Status)
	}

	return nil
}

func main() {
	jiraClient := &JiraClientImpl{}
	goAgentClient := &GoAgentClientImpl{}

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		fmt.Println(err)
		return
	}

	err = goAgentClient.SendStatus("SUCCESS")
	if err != nil {
		fmt.Println(err)
		return
	}
}