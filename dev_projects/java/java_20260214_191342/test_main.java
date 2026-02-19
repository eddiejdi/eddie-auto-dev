import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.types.TextFieldType;
import com.atlassian.jira.user.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

@Component
public class JavaAgentTest {

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ComponentManager componentManager;

    private JavaAgent agent;

    @BeforeEach
    public void setUp() {
        agent = new JavaAgent();
    }

    @Test
    public void testLogActivitySuccess() throws Exception {
        String issueKey = "JRA-100";
        String activity = "Starting development";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", activity);

        agent.logActivity(issueKey, activity);
        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(activity);
    }

    @Test
    public void testLogActivityFailure() throws Exception {
        String issueKey = "JRA-100";
        String activity = "";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", activity);

        agent.logActivity(issueKey, activity);
        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(activity);
    }

    @Test
    public void testMonitorActivitySuccess() throws Exception {
        String issueKey = "JRA-100";
        String activity = "Starting development";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", activity);

        agent.logActivity(issueKey, activity);
        agent.monitorActivity(issueKey, activity);

        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(activity);
    }

    @Test
    public void testMonitorActivityFailure() throws Exception {
        String issueKey = "JRA-100";
        String activity = "";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", activity);

        agent.logActivity(issueKey, activity);
        agent.monitorActivity(issueKey, activity);

        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(activity);
    }

    @Test
    public void testAlertProblemsSuccess() throws Exception {
        String issueKey = "JRA-100";
        String problemDescription = "System is down";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", problemDescription);

        agent.logActivity(issueKey, activity);
        agent.alertProblems(issueKey, problemDescription);

        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(problemDescription);
    }

    @Test
    public void testAlertProblemsFailure() throws Exception {
        String issueKey = "JRA-100";
        String problemDescription = "";

        Map<String, Object> fields = new HashMap<>();
        fields.put("Customfield_10100", problemDescription);

        agent.logActivity(issueKey, activity);
        agent.alertProblems(issueKey, problemDescription);

        Issue updatedIssue = componentManager.getIssueObject(issueKey);

        assert updatedIssue != null;
        assert updatedIssue.getFields().get("Customfield_10100").getValue().equals(problemDescription);
    }
}