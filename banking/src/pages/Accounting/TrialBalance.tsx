import _ from "@/lib/translate"
import { useState } from "react"
import { useFrappePostCall } from "frappe-react-sdk"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Loader2Icon } from "lucide-react"

type TrialRow = {
    account: string
    account_name: string
    debit: number
    credit: number
    opening_debit: number
    opening_credit: number
    closing_debit: number
    closing_credit: number
}

const TrialBalance = () => {
    const [company, setCompany] = useState<string>("")
    const { result, call, loading, error } = useFrappePostCall<{ message: TrialRow[] }>("run_doc_method")

    const runReport = () => {
        if (!company) return
        call({
            docs: { doctype: "Trial Balance" },
            method: "get_data",
            kwargs: { company, with_period_closing_entry: true },
        })
    }

    const rows: TrialRow[] = (result?.message as unknown as TrialRow[]) ?? []

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
                <Select value={company} onValueChange={setCompany}>
                    <SelectTrigger className="w-64">
                        <SelectValue placeholder={_("Select Company")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="CADRO Teknoloji A.Ş.">{_("CADRO Teknoloji A.Ş.")}</SelectItem>
                    </SelectContent>
                </Select>
                <Button onClick={runReport} disabled={loading || !company} size="sm">
                    {loading ? <Loader2Icon className="size-4 animate-spin" /> : null}
                    {_("Run")}
                </Button>
            </div>

            {error ? (
                <div className="p-4 text-destructive">{_("Failed to run trial balance.")}</div>
            ) : rows.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>{_("Account")}</TableHead>
                                <TableHead className="text-end">{_("Opening Debit")}</TableHead>
                                <TableHead className="text-end">{_("Opening Credit")}</TableHead>
                                <TableHead className="text-end">{_("Debit")}</TableHead>
                                <TableHead className="text-end">{_("Credit")}</TableHead>
                                <TableHead className="text-end">{_("Closing Debit")}</TableHead>
                                <TableHead className="text-end">{_("Closing Credit")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {rows.map((r, i) => (
                                <TableRow key={i}>
                                    <TableCell className="font-medium">{r.account_name ?? r.account}</TableCell>
                                    <TableCell className="text-end text-sm">{r.opening_debit?.toFixed(2) ?? "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.opening_credit?.toFixed(2) ?? "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.debit?.toFixed(2) ?? "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.credit?.toFixed(2) ?? "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.closing_debit?.toFixed(2) ?? "-"}</TableCell>
                                    <TableCell className="text-end text-sm">{r.closing_credit?.toFixed(2) ?? "-"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            ) : null}
        </div>
    )
}

export default TrialBalance
