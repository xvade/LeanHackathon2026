graph [
  directed 1
  node [
    id 0
    label "unsafe|constructors|global|Exists"
  ]
  node [
    id 1
    label "unsafe|tactic|global|Aesop.BuiltinRules.applyHyps"
  ]
  node [
    id 2
    label "safe|tactic|global|Aesop.BuiltinRules.rfl"
  ]
  node [
    id 3
    label "safe|tactic|global|Aesop.BuiltinRules.assumption"
  ]
  node [
    id 4
    label "unsafe|tactic|global|Aesop.BuiltinRules.ext"
  ]
  node [
    id 5
    label "unsafe|apply|global|Even.add"
  ]
  node [
    id 6
    label "unsafe|forward|global|Even.exists_add_self"
  ]
  node [
    id 7
    label "unsafe|apply|global|Even.sub"
  ]
  node [
    id 8
    label "unsafe|constructors|global|Or"
  ]
  node [
    id 9
    label "unsafe|apply|global|RingPreordering.eq_zero_of_mem_of_neg_mem"
  ]
  node [
    id 10
    label "safe|apply|global|ZeroMemClass.zero_mem"
  ]
  node [
    id 11
    label "unsafe|apply|global|div_mem"
  ]
  node [
    id 12
    label "unsafe|apply|global|nsmul_mem"
  ]
  node [
    id 13
    label "unsafe|apply|global|pow_mem"
  ]
  node [
    id 14
    label "unsafe|apply|global|sub_mem"
  ]
  node [
    id 15
    label "unsafe|apply|global|zpow_mem"
  ]
  node [
    id 16
    label "unsafe|apply|global|zsmul_mem"
  ]
  node [
    id 17
    label "unsafe|apply|global|AddMemClass.add_mem"
  ]
  node [
    id 18
    label "unsafe|apply|global|InvMemClass.inv_mem"
  ]
  node [
    id 19
    label "unsafe|apply|global|MulMemClass.mul_mem"
  ]
  node [
    id 20
    label "unsafe|apply|global|NegMemClass.neg_mem"
  ]
  node [
    id 21
    label "unsafe|apply|global|SMulMemClass.smul_mem"
  ]
  node [
    id 22
    label "unsafe|apply|global|StarMemClass.star_mem"
  ]
  node [
    id 23
    label "unsafe|apply|global|SubfieldClass.nnqsmul_mem"
  ]
  node [
    id 24
    label "unsafe|apply|global|SubfieldClass.qsmul_mem"
  ]
  node [
    id 25
    label "unsafe|apply|global|VAddMemClass.vadd_mem"
  ]
  node [
    id 26
    label "unsafe|apply|global|mul_neg_mem"
  ]
  node [
    id 27
    label "unsafe|apply|global|neg_mul_mem"
  ]
  node [
    id 28
    label "unsafe|apply|global|HasMemOrInvMem.inv_mem_of_notMem"
  ]
  node [
    id 29
    label "unsafe|apply|global|HasMemOrInvMem.mem_of_inv_notMem"
  ]
  node [
    id 30
    label "unsafe|apply|global|HasMemOrNegMem.mem_of_neg_notMem"
  ]
  node [
    id 31
    label "unsafe|apply|global|HasMemOrNegMem.neg_mem_of_notMem"
  ]
  node [
    id 32
    label "safe|apply|global|OneMemClass.one_mem"
  ]
  edge [
    source 0
    target 1
    weight 70.0
  ]
  edge [
    source 1
    target 29
    weight 2.0
  ]
  edge [
    source 1
    target 30
    weight 2.0
  ]
  edge [
    source 2
    target 1
    weight 55.0
  ]
  edge [
    source 2
    target 4
    weight 47.0
  ]
  edge [
    source 2
    target 9
    weight 8.0
  ]
  edge [
    source 3
    target 1
    weight 7.0
  ]
  edge [
    source 3
    target 4
    weight 5.0
  ]
  edge [
    source 3
    target 9
    weight 2.0
  ]
  edge [
    source 4
    target 1
    weight 3.0
  ]
  edge [
    source 5
    target 1
    weight 1.0
  ]
  edge [
    source 5
    target 6
    weight 1.0
  ]
  edge [
    source 7
    target 1
    weight 1.0
  ]
  edge [
    source 7
    target 6
    weight 1.0
  ]
  edge [
    source 8
    target 1
    weight 37.0
  ]
  edge [
    source 10
    target 11
    weight 1.0
  ]
  edge [
    source 10
    target 12
    weight 1.0
  ]
  edge [
    source 10
    target 13
    weight 1.0
  ]
  edge [
    source 10
    target 14
    weight 1.0
  ]
  edge [
    source 10
    target 15
    weight 1.0
  ]
  edge [
    source 10
    target 16
    weight 1.0
  ]
  edge [
    source 10
    target 17
    weight 1.0
  ]
  edge [
    source 10
    target 18
    weight 1.0
  ]
  edge [
    source 10
    target 19
    weight 1.0
  ]
  edge [
    source 10
    target 20
    weight 1.0
  ]
  edge [
    source 10
    target 21
    weight 1.0
  ]
  edge [
    source 10
    target 22
    weight 1.0
  ]
  edge [
    source 10
    target 23
    weight 1.0
  ]
  edge [
    source 10
    target 24
    weight 1.0
  ]
  edge [
    source 10
    target 25
    weight 1.0
  ]
  edge [
    source 10
    target 3
    weight 1.0
  ]
  edge [
    source 10
    target 26
    weight 1.0
  ]
  edge [
    source 10
    target 27
    weight 1.0
  ]
  edge [
    source 10
    target 1
    weight 1.0
  ]
  edge [
    source 10
    target 28
    weight 1.0
  ]
  edge [
    source 10
    target 29
    weight 1.0
  ]
  edge [
    source 10
    target 30
    weight 1.0
  ]
  edge [
    source 10
    target 31
    weight 1.0
  ]
  edge [
    source 32
    target 11
    weight 2.0
  ]
  edge [
    source 32
    target 12
    weight 2.0
  ]
  edge [
    source 32
    target 13
    weight 2.0
  ]
  edge [
    source 32
    target 14
    weight 2.0
  ]
  edge [
    source 32
    target 15
    weight 2.0
  ]
  edge [
    source 32
    target 16
    weight 2.0
  ]
  edge [
    source 32
    target 17
    weight 2.0
  ]
  edge [
    source 32
    target 18
    weight 2.0
  ]
  edge [
    source 32
    target 19
    weight 2.0
  ]
  edge [
    source 32
    target 20
    weight 2.0
  ]
  edge [
    source 32
    target 21
    weight 2.0
  ]
  edge [
    source 32
    target 22
    weight 2.0
  ]
  edge [
    source 32
    target 23
    weight 2.0
  ]
  edge [
    source 32
    target 24
    weight 2.0
  ]
  edge [
    source 32
    target 25
    weight 2.0
  ]
  edge [
    source 32
    target 26
    weight 2.0
  ]
  edge [
    source 32
    target 27
    weight 2.0
  ]
  edge [
    source 32
    target 1
    weight 2.0
  ]
  edge [
    source 32
    target 28
    weight 2.0
  ]
  edge [
    source 32
    target 29
    weight 2.0
  ]
  edge [
    source 32
    target 30
    weight 2.0
  ]
  edge [
    source 32
    target 31
    weight 2.0
  ]
]
