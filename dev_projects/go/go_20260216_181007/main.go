package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Fields     map[string]interface{} `json:"fields"`
}

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	url := fmt.Sprintf("%s/rest/api/2/issue", jiraURL)
	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}

	req.SetBasicAuth(username, password)

	req.Header.Set("Content-Type", "application/json")

	payload := map[string]interface{}{
		"fields": map[string]interface{}{
			"project": map[string]string{
				"key": projectKey,
			},
			"summary": summary,
			"description": description,
		},
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("Error marshaling JSON payload: %v", err)
	}

	req.Body = ioutil.NopCloser(bytes.NewBuffer(jsonPayload))

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 201 {
		bodyBytes, _ := ioutil.ReadAll(resp.Body)
		return nil, fmt.Errorf("Error creating Jira issue: %s", bodyBytes)
	}

	var issue JiraIssue
	err = json.NewDecoder(resp.Body).Decode(&issue)
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