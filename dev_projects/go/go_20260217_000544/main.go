package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue
type JiraIssue struct {
	ID          string `json:"id"`
	Key         string `json:"key"`
	Project     Project  `json:"project"`
	Summary      string `json:"summary"`
	Description string `json:"description"`
}

// Project represents the project associated with an issue
type Project struct {
	Key string `json:"key"`
	Name string `json:"name"`
}

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(fmt.Sprintf(`{
		"fields": {
			"project": {
				"key": "%s"
			},
			"summary": "%s",
			"description": "%s"
		}
	}`, projectKey, summary, description)))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}

	req.SetBasicAuth(username, password)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error making request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("Failed to create issue. Status code: %d", resp.StatusCode)
	}

	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("Error reading response body: %v", err)
	}

	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
	}

	return &issue, nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err != nil {
		fmt.Println("Error creating Jira issue:", err)
		return
	}

	fmt.Printf("Created Issue: %+v\n", createdIssue)
}