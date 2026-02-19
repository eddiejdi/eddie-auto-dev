package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	url    string
	token  string
}

// NewJiraClient cria uma nova instância do JiraClient
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url:    url,
		token:  token,
	}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(title, description string) error {
	req, err := http.NewRequest("POST", jc.url+"/rest/api/2/issue", nil)
	if err != nil {
		return fmt.Errorf("failed to create issue: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", jc.token))

	jiraIssue := map[string]interface{}{
		"fields": map[string]interface{}{
			"title":    title,
			"description": description,
		},
	}

	jsonBody, err := json.Marshal(jiraIssue)
	if err != nil {
		return fmt.Errorf("failed to marshal JSON: %w", err)
	}

	req.Body = io.NopCloser(bytes.NewBuffer(jsonBody))

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("issue creation failed with status code %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

func main() {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "your-api-token")

	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		fmt.Println(err)
		return
	}
}