package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents the structure of a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary  string `json:"summary"`
	Description string `json:"description"`
}

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	// Prepare the request
	req, err := http.NewRequest("POST", jiraURL, nil)
	if err != nil {
		return nil, fmt.Errorf("Error creating HTTP request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	// Create the JSON payload
	payload := map[string]string{
		"fields": json.RawMessage(`{"project": {"key": "` + projectKey + `"}, "summary": "` + summary + `", "description": "` + description + `"}}`),
	}

	// Encode the payload to JSON
	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("Error marshaling JSON payload: %v", err)
	}

	// Set the request body
	req.Body = ioutil.NopCloser(bytes.NewBuffer(jsonPayload))

	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Check if the response status code is 201 (Created)
	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("Failed to create Jira issue. Status code: %d", resp.StatusCode)
	}

	// Read the response body
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Error reading response body:", err)
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		fmt.Println("Error parsing JSON response:", err)
		return nil, fmt.Errorf("Error creating Jira issue: %v", err)
	}

	return &issue, nil
}