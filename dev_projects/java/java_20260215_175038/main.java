import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClients;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.input.IssueInput;
import com.atlassian.jira.client.api.domain.output.IssueField;
import com.atlassian.jira.client.api.domain.output.IssueFieldValues;
import com.atlassian.jira.client.api.domain.output.IssueFieldValue;
import com.atlassian.jira.client.api.domain.output.IssueFields;
import com.atlassian.jira.client.api.domain.output.IssueStatus;
import com.atlassian.jira.client.api.domain.output.Project;
import com.atlassian.jira.client.api.domain.output.User;
import com.atlassian.jira.client.api.exception.JiraException;
import org.springframework.stereotype.Service;

@Service
public class JiraIntegrationService {

    private final JiraClient jiraClient;

    public JiraIntegrationService() {
        this.jiraClient = JiraClients.create("https://your-jira-instance.com", "your-username", "your-password");
    }

    public void createIssue(String projectKey, String issueType, String summary) throws JiraException {
        IssueInput issueInput = new IssueInput();
        issueInput.setProject(projectKey);
        issueInput.setType(issueType);
        issueInput.setSummary(summary);

        Issue createdIssue = jiraClient.createIssue(issueInput);
        System.out.println("Created issue: " + createdIssue.getId());
    }

    public void updateIssue(String issueId, String summary) throws JiraException {
        IssueInput issueInput = new IssueInput();
        issueInput.setId(issueId);
        issueInput.setSummary(summary);

        jiraClient.updateIssue(issueInput);
        System.out.println("Updated issue: " + issueId);
    }

    public void deleteIssue(String issueId) throws JiraException {
        jiraClient.deleteIssue(issueId);
        System.out.println("Deleted issue: " + issueId);
    }
}