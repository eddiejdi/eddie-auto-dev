import com.atlassian.jira.rest.client.JiraRestClient;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.api.IssueService;
import com.atlassian.jira.rest.client.api.model.Issue;
import com.atlassian.jira.rest.client.api.model.IssueFieldValues;
import com.atlassian.jira.rest.client.api.model.fields.FieldValue;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.atlassian.net";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraRestClient client = new JiraRestClient.Builder(JIRA_URL, new BasicHttpAuthenticationHandler(USERNAME, PASSWORD)).build()) {

            IssueService issueService = client.getIssueService();

            // Create a new issue
            Issue newIssue = createNewIssue(issueService);

            // Add fields to the issue
            addFieldsToIssue(newIssue, issueService);

            // Update the issue with field values
            updateIssueWithFieldValues(newIssue, issueService);

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static Issue createNewIssue(IssueService issueService) throws IOException {
        Issue newIssue = new Issue.Builder()
                .setProjectKey("YOUR_PROJECT_KEY")
                .setSummary("Test Issue")
                .setDescription("This is a test issue created by the Java Agent Jira Integration.")
                .build();

        return issueService.createIssue(newIssue);
    }

    private static void addFieldsToIssue(Issue newIssue, IssueService issueService) throws IOException {
        List<FieldValue> fields = createFieldValues();
        issueService.updateIssueFields(newIssue.getId(), fields);
    }

    private static List<FieldValue> createFieldValues() {
        FieldValue title = new FieldValue.Builder()
                .setFieldId("summary")
                .setValue("Test Issue")
                .build();

        FieldValue description = new FieldValue.Builder()
                .setFieldId("description")
                .setValue("This is a test issue created by the Java Agent Jira Integration.")
                .build();

        return List.of(title, description);
    }

    private static void updateIssueWithFieldValues(Issue newIssue, IssueService issueService) throws IOException {
        List<FieldValue> fields = createFieldValues();
        issueService.updateIssueFields(newIssue.getId(), fields);
    }
}