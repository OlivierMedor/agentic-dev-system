# Round Trip Report

## Scenario A

validated_safe response
-> plan
-> dry run
-> apply
-> new revision
-> source superseded
-> children ready
-> explicit resume
-> leases created

## Scenario B

approval_required response
-> exact approval verified
-> plan
-> apply
-> explicit resume

## Scenario C

plan on R3
-> active revision becomes R4
-> apply rejected
-> R4 remains active

## Scenario D

proposed R5 write begins
-> injected failure
-> R4 remains active
-> partial R5 not activated

## Scenario E

task lease created on R4
-> active revision becomes R5
-> R4 worker publishes
-> result rejected or quarantined

## Scenario F

apply creates R5
-> explicit resume
-> operator stops
-> rollback restores R4
-> evidence preserved
-> Git work products reported

## Scenario G

pointer changed to R5
-> process stops before application status update
-> recover identifies mismatch
-> safely reconciles status

