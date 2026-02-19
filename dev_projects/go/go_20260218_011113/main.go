import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue structure
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to the Jira API to create a new issue
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	// Create a new HTTP client
	client := &http.Client{}

	// Prepare the request body for creating an issue
	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "%s"
		}
	}`, projectKey, summary, description)

	// Set the request headers
	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	// Send the request
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	// Read the response body
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("Error reading response body: %v", err)
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {

INSTRUÇÕES:
1. Implemente TODAS as funcionalidades listadas nos requisitos
2. Crie classes e funções bem estruturadas
3. Inclua docstrings explicando cada função
4. Adicione tratamento de erros apropriado
5. O código deve ser completo e executável
6. Se for CLI, inclua if __name__ == "__main__":

Forneça APENAS o código go completo, sem explicações.